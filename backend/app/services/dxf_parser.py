"""
DXF Parser Service — Complete Rewrite
======================================
Handles real AutoCAD architectural DXF files correctly.

Pipeline:
  1. Decode DXF bytes (UTF-8 / CP1252 / Latin-1)
  2. Read $INSUNITS for unit auto-detection
  3. Use ezdxf to iterate modelspace + all BLOCK references
  4. Extract raw geometry: LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, SPLINE
  5. Collect all segments as (x1,y1)→(x2,y2) with layer info
  6. Build closed loops from connected segments (snap tolerance)
  7. Filter out sheet/title/annotation boundaries
  8. Identify outer building footprint = largest valid closed area
  9. Detect walls, doors, windows independently
 10. Return rich result with diagnostics

Key fixes vs old parser:
  - Resolves INSERT/BLOCK references (geometry was hidden there)
  - Handles OLE2FRAME gracefully (warns, does not fabricate area)
  - Builds loops from LINE chains (not just closed LWPOLYLINE)
  - Filters sheet border from building footprint
  - Reports out-to-out building/slab area correctly
"""
from __future__ import annotations
import io
import re
import math
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────
M2_TO_FT2 = 10.7639
M_TO_FT   = 3.28084

# Layers that typically belong to title block / sheet border — skip for building area
_TITLEBLOCK_LAYER_HINTS = {
    "titleblock", "title", "titleblk", "title_block", "border", "sheet",
    "defpoints", "viewport", "vport", "frame", "tb", "title-block",
    "title block", "drawing border", "logo", "revision", "rev",
}

# Layers that suggest architectural building geometry
_ARCH_LAYER_HINTS = {
    "wall", "walls", "a-wall", "arch", "archwall", "ext_wall", "int_wall",
    "partition", "slab", "floor", "structure", "struct", "column", "col",
    "beam", "room", "outline", "boundary", "bldg", "building", "footprint",
    "plan", "gf", "ff", "roof", "terrace", "0",  # layer 0 is default
}

# Door/window block name hints
_DOOR_HINTS   = {"door", "dr", "pintu", "d-", "swng", "swing"}
_WINDOW_HINTS = {"window", "win", "casement", "jendela", "w-", "wdw"}


# ─────────────────────────────────────────────────────
# Utility geometry functions
# ─────────────────────────────────────────────────────

def _dist(a, b) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)


def _shoelace(pts) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = sum(pts[i][0]*pts[(i+1)%n][1] - pts[(i+1)%n][0]*pts[i][1] for i in range(n))
    return abs(s) / 2.0


def _arc_to_segments(cx, cy, r, a1_deg, a2_deg, num_seg=24):
    """Approximate arc as polyline segments."""
    a1 = math.radians(a1_deg)
    a2 = math.radians(a2_deg)
    if a2 <= a1:
        a2 += 2 * math.pi
    pts = []
    for k in range(num_seg + 1):
        t = a1 + (a2 - a1) * k / num_seg
        pts.append((cx + r*math.cos(t), cy + r*math.sin(t)))
    return pts


def _circle_to_pts(cx, cy, r, num_seg=36):
    pts = []
    for k in range(num_seg):
        t = 2 * math.pi * k / num_seg
        pts.append((cx + r*math.cos(t), cy + r*math.sin(t)))
    return pts


# ─────────────────────────────────────────────────────
# Unit detection
# ─────────────────────────────────────────────────────

_INSUNITS_MAP = {
    0:  ("unknown",  None),
    1:  ("inches",   0.0254),
    2:  ("feet",     0.3048),
    3:  ("miles",    1609.344),
    4:  ("mm",       0.001),
    5:  ("cm",       0.01),
    6:  ("m",        1.0),
    7:  ("km",       1000.0),
    8:  ("microin",  2.54e-8),
    9:  ("mils",     2.54e-5),
    10: ("yards",    0.9144),
    11: ("angstrom", 1e-10),
    12: ("nm",       1e-9),
    13: ("micron",   1e-6),
    14: ("dm",       0.1),
    15: ("dam",      10.0),
    16: ("hm",       100.0),
    17: ("gigameter",1e9),
    18: ("AU",       1.496e11),
    19: ("ly",       9.461e15),
    20: ("parsec",   3.086e16),
}

_MANUAL_SF = {"mm": 0.001, "cm": 0.01, "m": 1.0, "ft": 0.3048, "in": 0.0254}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def _get_insunits(lines) -> int:
    for i, l in enumerate(lines):
        if l.strip() == "$INSUNITS" and i + 2 < len(lines):
            try:
                return int(lines[i + 2].strip())
            except Exception:
                pass
    return 0


def _extract_entities_section(lines) -> list:
    start = None
    for i, l in enumerate(lines):
        if l.strip() == "ENTITIES":
            start = i
            break
    if start is None:
        return lines
    end = None
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "ENDSEC":
            end = i
            break
    return lines[start:end+1] if end else lines[start:]


# ─────────────────────────────────────────────────────
# Segment collection — raw geometry → list of segments
# ─────────────────────────────────────────────────────

class Segment:
    __slots__ = ("x1","y1","x2","y2","layer","etype")
    def __init__(self, x1,y1,x2,y2, layer="0", etype="LINE"):
        self.x1=x1; self.y1=y1; self.x2=x2; self.y2=y2
        self.layer=layer.upper(); self.etype=etype

    def length(self):
        return _dist((self.x1,self.y1),(self.x2,self.y2))

    def endpoints(self):
        return (self.x1,self.y1), (self.x2,self.y2)


def _layer_is_titleblock(layer: str) -> bool:
    l = layer.lower().strip()
    return any(h in l for h in _TITLEBLOCK_LAYER_HINTS)


def _layer_is_arch(layer: str) -> bool:
    l = layer.lower().strip()
    if l == "0":
        return True
    return any(h in l for h in _ARCH_LAYER_HINTS)


# ─────────────────────────────────────────────────────
# ezdxf-based geometry extraction
# ─────────────────────────────────────────────────────

def _collect_segments_ezdxf(dxf_bytes: bytes) -> tuple[list[Segment], dict, list[str]]:
    """
    Use ezdxf to iterate modelspace + blocks.
    Returns (segments, entity_counts, warnings).
    """
    segments: list[Segment] = []
    entity_counts: dict = {}
    warnings: list[str] = []
    door_count   = 0
    window_count = 0
    insert_count = 0

    try:
        import ezdxf
        from ezdxf.math import Vec2
    except ImportError:
        warnings.append("ezdxf not installed — falling back to raw parser.")
        return segments, entity_counts, warnings

    try:
        doc = ezdxf.from_bytes(dxf_bytes)
    except Exception as e:
        warnings.append(f"ezdxf could not open file: {e}")
        return segments, entity_counts, warnings

    msp = doc.modelspace()

    def _process_entity(e, xform=None):
        nonlocal door_count, window_count, insert_count
        etype = e.dxftype()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

        try:
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "0"
        except Exception:
            layer = "0"

        # Skip pure OLE frames
        if etype == "OLE2FRAME":
            return

        # ── LINE ─────────────────────────────────────
        if etype == "LINE":
            try:
                p1 = e.dxf.start
                p2 = e.dxf.end
                if xform:
                    p1 = xform @ p1
                    p2 = xform @ p2
                seg = Segment(p1.x, p1.y, p2.x, p2.y, layer, "LINE")
                if seg.length() > 1e-9:
                    segments.append(seg)
            except Exception:
                pass

        # ── LWPOLYLINE ────────────────────────────────
        elif etype == "LWPOLYLINE":
            try:
                pts = list(e.get_points())
                if len(pts) < 2:
                    return
                if xform:
                    pts = [(xform @ (p[0], p[1], 0))[:2] for p in pts]
                else:
                    pts = [(p[0], p[1]) for p in pts]
                closed = e.closed or (e.dxf.hasattr("flags") and bool(e.dxf.flags & 1))
                if closed:
                    pts = list(pts) + [pts[0]]
                for k in range(len(pts)-1):
                    seg = Segment(pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1], layer, "LWPOLYLINE")
                    if seg.length() > 1e-9:
                        segments.append(seg)
            except Exception:
                pass

        # ── POLYLINE (old-style) ──────────────────────
        elif etype == "POLYLINE":
            try:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                if len(pts) < 2:
                    return
                if xform:
                    pts = [(xform @ (p[0], p[1], 0))[:2] for p in pts]
                closed = bool(e.dxf.flags & 1) if e.dxf.hasattr("flags") else False
                if closed:
                    pts = pts + [pts[0]]
                for k in range(len(pts)-1):
                    seg = Segment(pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1], layer, "POLYLINE")
                    if seg.length() > 1e-9:
                        segments.append(seg)
            except Exception:
                pass

        # ── ARC ───────────────────────────────────────
        elif etype == "ARC":
            try:
                cx = e.dxf.center.x
                cy = e.dxf.center.y
                r  = e.dxf.radius
                a1 = e.dxf.start_angle
                a2 = e.dxf.end_angle
                if xform:
                    c = xform @ (cx, cy, 0)
                    cx, cy = c[0], c[1]
                arc_pts = _arc_to_segments(cx, cy, r, a1, a2, num_seg=16)
                for k in range(len(arc_pts)-1):
                    seg = Segment(arc_pts[k][0], arc_pts[k][1],
                                  arc_pts[k+1][0], arc_pts[k+1][1], layer, "ARC")
                    if seg.length() > 1e-9:
                        segments.append(seg)
            except Exception:
                pass

        # ── CIRCLE ────────────────────────────────────
        elif etype == "CIRCLE":
            try:
                cx = e.dxf.center.x
                cy = e.dxf.center.y
                r  = e.dxf.radius
                if xform:
                    c = xform @ (cx, cy, 0)
                    cx, cy = c[0], c[1]
                cpts = _circle_to_pts(cx, cy, r, 24) + [_circle_to_pts(cx, cy, r, 24)[0]]
                for k in range(len(cpts)-1):
                    seg = Segment(cpts[k][0], cpts[k][1],
                                  cpts[k+1][0], cpts[k+1][1], layer, "CIRCLE")
                    if seg.length() > 1e-9:
                        segments.append(seg)
            except Exception:
                pass

        # ── SPLINE (sample it) ────────────────────────
        elif etype == "SPLINE":
            try:
                pts_iter = list(e.approximate(segments=20))
                if xform:
                    pts_iter = [(xform @ (p.x, p.y, 0))[:2] for p in pts_iter]
                else:
                    pts_iter = [(p.x, p.y) for p in pts_iter]
                for k in range(len(pts_iter)-1):
                    seg = Segment(pts_iter[k][0], pts_iter[k][1],
                                  pts_iter[k+1][0], pts_iter[k+1][1], layer, "SPLINE")
                    if seg.length() > 1e-9:
                        segments.append(seg)
            except Exception:
                pass

        # ── INSERT (block reference) ──────────────────
        elif etype == "INSERT":
            insert_count += 1
            try:
                bname = e.dxf.name.upper() if e.dxf.hasattr("name") else ""
                blayer = layer.upper()
                combined = bname + " " + blayer
                if any(h in combined.lower() for h in _DOOR_HINTS):
                    door_count += 1
                elif any(h in combined.lower() for h in _WINDOW_HINTS):
                    window_count += 1
                # Explode block geometry
                try:
                    for child in e.virtual_entities():
                        _process_entity(child)
                except Exception:
                    pass
            except Exception:
                pass

    # Process all modelspace entities
    try:
        for ent in msp:
            _process_entity(ent)
    except Exception as ex:
        warnings.append(f"Error iterating modelspace: {ex}")

    entity_counts["_doors"]   = door_count
    entity_counts["_windows"] = window_count
    entity_counts["_inserts"] = insert_count

    return segments, entity_counts, warnings


# ─────────────────────────────────────────────────────
# Fallback raw-text parser (when ezdxf fails)
# ─────────────────────────────────────────────────────

def _collect_segments_raw(lines: list[str]) -> tuple[list[Segment], dict, list[str]]:
    """Pure-text fallback parser for when ezdxf is unavailable or crashes."""
    segments: list[Segment] = []
    entity_counts: dict = {}
    warnings  = ["Using fallback raw text parser (ezdxf unavailable)."]
    door_count   = 0
    window_count = 0
    n = len(lines)
    i = 0

    while i < n:
        if lines[i].strip() == "0" and i + 1 < n:
            etype = lines[i+1].strip().upper()
            if not etype or etype in ("SECTION","ENDSEC","EOF"):
                i += 1; continue
            entity_counts[etype] = entity_counts.get(etype, 0) + 1

            # Read all group codes for this entity
            gc: dict = {}
            pts10: list = []
            pts20: list = []
            layer_val = "0"
            j = i + 2
            while j < n:
                c = lines[j].strip()
                if c == "0": break
                if j+1 < n:
                    v = lines[j+1].strip()
                    if c == "8":
                        layer_val = v
                    elif c == "10":
                        try: pts10.append(float(v))
                        except: pass
                    elif c == "20":
                        try: pts20.append(float(v))
                        except: pass
                    else:
                        try: gc[c] = float(v)
                        except: gc[c] = v
                j += 2

            if etype == "LINE" and len(pts10) >= 2 and len(pts20) >= 2:
                seg = Segment(pts10[0], pts20[0], pts10[1], pts20[1], layer_val, "LINE")
                if seg.length() > 1e-9:
                    segments.append(seg)

            elif etype == "LWPOLYLINE" and len(pts10) >= 2 and len(pts20) >= 2:
                flags = int(gc.get("70", 0))
                pts = list(zip(pts10, pts20))
                closed = bool(flags & 1)
                if closed:
                    pts = pts + [pts[0]]
                for k in range(len(pts)-1):
                    seg = Segment(pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1], layer_val, "LWPOLYLINE")
                    if seg.length() > 1e-9:
                        segments.append(seg)

            elif etype == "INSERT":
                bname = str(gc.get("2", "")).upper()
                combined = bname + " " + layer_val
                if any(h in combined.lower() for h in _DOOR_HINTS):
                    door_count += 1
                elif any(h in combined.lower() for h in _WINDOW_HINTS):
                    window_count += 1

        i += 1

    entity_counts["_doors"]   = door_count
    entity_counts["_windows"] = window_count
    return segments, entity_counts, warnings


# ─────────────────────────────────────────────────────
# Loop builder — connect segments into closed polygons
# ─────────────────────────────────────────────────────

def _snap_point(p, tol: float) -> tuple:
    """Round to tolerance grid for snapping."""
    if tol <= 0:
        return p
    return (round(p[0]/tol)*tol, round(p[1]/tol)*tol)


def _build_loops(segments: list[Segment], tol: float = 10.0) -> list[list[tuple]]:
    """
    Join connected segments into closed loops.
    tol: endpoint snap tolerance in drawing units.
    Uses greedy chain-building: start from each unvisited segment,
    follow connected endpoints until chain closes or dead-ends.
    """
    if not segments:
        return []

    # Build adjacency: snapped endpoint → list of segment indices
    from collections import defaultdict
    adj: dict = defaultdict(list)
    segs_ep = []
    for idx, seg in enumerate(segments):
        p1 = _snap_point((seg.x1, seg.y1), tol)
        p2 = _snap_point((seg.x2, seg.y2), tol)
        segs_ep.append((p1, p2))
        adj[p1].append(idx)
        adj[p2].append(idx)

    used  = set()
    loops = []

    def _try_build_chain(start_idx):
        if start_idx in used:
            return None
        chain_pts = [segs_ep[start_idx][0], segs_ep[start_idx][1]]
        chain_segs = {start_idx}
        used.add(start_idx)
        head = segs_ep[start_idx][0]
        tail = segs_ep[start_idx][1]

        for _ in range(len(segments)):
            # Try to extend from tail
            candidates = [i for i in adj[tail] if i not in chain_segs]
            if not candidates:
                break
            # Pick the candidate that continues most naturally
            next_idx = candidates[0]
            p1, p2 = segs_ep[next_idx]
            if p1 == tail:
                next_pt = p2
            elif p2 == tail:
                next_pt = p1
            else:
                break
            chain_pts.append(next_pt)
            chain_segs.add(next_idx)
            used.add(next_idx)
            tail = next_pt
            if tail == head and len(chain_pts) >= 4:
                return chain_pts[:-1]  # closed — remove duplicate endpoint
        return None

    for idx in range(len(segments)):
        if idx in used:
            continue
        loop = _try_build_chain(idx)
        if loop and len(loop) >= 3:
            loops.append(loop)

    return loops


def _loop_bounds(loop: list[tuple]) -> tuple:
    """Return (minx, miny, maxx, maxy, width, height, cx, cy)."""
    xs = [p[0] for p in loop]
    ys = [p[1] for p in loop]
    mn_x, mx_x = min(xs), max(xs)
    mn_y, mx_y = min(ys), max(ys)
    return mn_x, mn_y, mx_x, mx_y, mx_x-mn_x, mx_y-mn_y, (mn_x+mx_x)/2, (mn_y+mn_y)/2


def _all_segments_bounds(segments: list[Segment]) -> tuple:
    """Bounding box of all geometry."""
    if not segments:
        return 0,0,0,0,0,0
    xs = [s.x1 for s in segments] + [s.x2 for s in segments]
    ys = [s.y1 for s in segments] + [s.y2 for s in segments]
    mn_x, mx_x = min(xs), max(xs)
    mn_y, mx_y = min(ys), max(ys)
    return mn_x, mn_y, mx_x, mx_y, mx_x-mn_x, mx_y-mn_y


# ─────────────────────────────────────────────────────
# Building boundary detection
# ─────────────────────────────────────────────────────

def _is_sheet_border(loop: list[tuple], all_bounds: tuple, sf: float) -> bool:
    """
    Heuristic: return True if this loop is likely a sheet/title/paper border.
    A sheet border typically:
    - Is very close in size to the total drawing extents
    - Is near-rectangular
    - Has area > 80% of bounding box (nearly empty interior)
    """
    mn_x, mn_y, mx_x, mx_y, total_w, total_h = all_bounds
    if total_w < 1e-6 or total_h < 1e-6:
        return False

    lb = _loop_bounds(loop)
    lw, lh = lb[4], lb[5]

    # If loop fills >85% of the total drawing extent → likely sheet border
    if total_w > 0 and total_h > 0:
        w_ratio = lw / total_w
        h_ratio = lh / total_h
        if w_ratio > 0.85 and h_ratio > 0.85:
            return True

    # If loop dimensions in metres are typical A0/A1 sheet sizes (>600mm wide)
    lw_m = lw * sf
    lh_m = lh * sf
    # A0 = 1189×841mm, A1 = 841×594mm, A2 = 594×420mm
    if lw_m > 0.5 and lh_m > 0.3:  # sheet-like in metres
        area_m2 = _shoelace(loop) * sf * sf
        # If it's a ~A-series sheet size with very low geometry density → sheet border
        if (0.2 < lw_m < 2.0) and (0.1 < lh_m < 1.5):
            # Typical architectural sheet sizes
            return True

    return False


def _score_loop_as_building(loop: list[tuple], area: float, sf: float,
                             layer_hint: str = "") -> float:
    """
    Score how likely a loop is the building footprint.
    Higher = more likely building.
    """
    score = area  # base: larger is better

    layer = layer_hint.lower()

    # Boost if layer name suggests architecture
    if any(h in layer for h in _ARCH_LAYER_HINTS):
        score *= 2.0

    # Penalize if layer suggests title block
    if _layer_is_titleblock(layer):
        score *= 0.01

    # Penalize if it's likely a sheet border (checked separately)
    # Penalize very thin loops (dimension lines, hatching)
    lb = _loop_bounds(loop)
    lw, lh = lb[4], lb[5]
    if lw > 0 and lh > 0:
        aspect = max(lw, lh) / min(lw, lh)
        if aspect > 20:  # very elongated → likely a line artifact
            score *= 0.1

    return score


# ─────────────────────────────────────────────────────
# Wall length extraction
# ─────────────────────────────────────────────────────

def _extract_wall_lengths(segments: list[Segment], sf: float) -> dict:
    """
    Sum up wall lengths from segments on WALL-like layers.
    Also returns total of ALL LINE segments as fallback.
    """
    ext_wall = 0.0
    int_wall = 0.0
    total_all_lines = 0.0

    ext_hints = {"ext", "external", "outer", "outside", "extwall", "ext_wall", "outer_wall"}
    int_hints = {"int", "internal", "inner", "inside", "intwall", "int_wall", "partition"}
    wall_hints = {"wall", "walls", "a-wall", "dinding"}

    for seg in segments:
        if seg.etype not in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC"):
            continue
        L = seg.length() * sf
        total_all_lines += L
        layer = seg.layer.lower()
        is_wall = any(h in layer for h in wall_hints) or layer == "0"
        if is_wall:
            if any(h in layer for h in ext_hints):
                ext_wall += L
            elif any(h in layer for h in int_hints):
                int_wall += L
            else:
                ext_wall += L * 0.5
                int_wall += L * 0.5

    return {
        "external_m": round(ext_wall, 3),
        "internal_m": round(int_wall, 3),
        "total_m":    round(ext_wall + int_wall, 3),
        "all_lines_m": round(total_all_lines, 3),
    }


# ─────────────────────────────────────────────────────
# Main result class
# ─────────────────────────────────────────────────────

class DXFParseResult:
    def __init__(self):
        # Primary result
        self.building_footprint_area_m2: float   = 0.0
        self.building_footprint_area_ft2: float  = 0.0
        self.boundary_perimeter_m: float          = 0.0
        self.boundary_perimeter_ft: float         = 0.0
        self.slab_area_m2: float                  = 0.0  # = footprint for BOQ

        # Walls
        self.external_wall_length_m: float  = 0.0
        self.internal_wall_length_m: float  = 0.0
        self.total_wall_length_m: float     = 0.0

        # Openings
        self.num_doors: int    = 0
        self.num_windows: int  = 0

        # All boundary candidates
        self.boundary_candidates: list[dict] = []

        # Room areas
        self.rooms: list[dict] = []

        # Diagnostics
        self.diagnostics: dict = {}
        self.warnings: list[str] = []
        self.scale_factor: float = 1.0
        self.entity_counts: dict = {}
        self.units_detected: str = "unknown"
        self.units_used: str = "mm"

        # Legacy (for backward compat with old API)
        self.total_floor_area_m2: float = 0.0

    def to_dict(self) -> dict:
        return {
            # Primary BOQ values
            "building_footprint_area_m2":  round(self.building_footprint_area_m2, 3),
            "building_footprint_area_ft2": round(self.building_footprint_area_ft2, 3),
            "boundary_perimeter_m":        round(self.boundary_perimeter_m, 3),
            "boundary_perimeter_ft":       round(self.boundary_perimeter_ft, 3),
            "slab_area_m2":                round(self.slab_area_m2, 3),
            # Legacy
            "total_floor_area_m2":         round(self.building_footprint_area_m2, 3),
            "total_wall_length_m":         round(self.total_wall_length_m, 3),
            # Walls
            "external_wall_length_m":      round(self.external_wall_length_m, 3),
            "internal_wall_length_m":      round(self.internal_wall_length_m, 3),
            # Openings
            "num_doors":                   self.num_doors,
            "num_windows":                 self.num_windows,
            # Candidates & rooms
            "boundary_candidates":         self.boundary_candidates,
            "rooms":                       self.rooms,
            # Meta
            "scale_factor":                self.scale_factor,
            "entity_counts":               self.entity_counts,
            "units_detected":              self.units_detected,
            "units_used":                  self.units_used,
            "diagnostics":                 self.diagnostics,
            "warnings":                    self.warnings,
        }


# ─────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────

def parse_dxf_bytes(file_bytes: bytes, units: str = "mm") -> DXFParseResult:
    """
    Full DXF parsing pipeline.
    Returns DXFParseResult with building footprint area, wall lengths, etc.
    """
    result = DXFParseResult()
    result.units_used = units

    manual_sf = _MANUAL_SF.get(units.lower(), 0.001)

    # ── Decode ────────────────────────────────────────
    text  = _decode(file_bytes)
    lines = text.splitlines()

    # ── Read INSUNITS ─────────────────────────────────
    insunits = _get_insunits(lines)
    unit_name, auto_sf = _INSUNITS_MAP.get(insunits, ("unknown", None))
    result.units_detected = unit_name

    if auto_sf is not None:
        sf = auto_sf
        result.scale_factor = sf
        if unit_name != units.lower():
            result.warnings.append(
                f"Auto-detected drawing units: {unit_name} (DXF $INSUNITS={insunits}). "
                f"You selected '{units}'. Using auto-detected value. "
                f"If result seems wrong, try changing Drawing Units to '{unit_name}'."
            )
        else:
            result.warnings.append(f"Drawing units confirmed: {unit_name}")
    else:
        sf = manual_sf
        result.scale_factor = sf
        result.warnings.append(
            f"$INSUNITS not set (value={insunits}). Using user-selected units: {units}. "
            "If areas seem wrong, try a different unit selection."
        )

    # ── Count raw entity types for diagnostics ────────
    raw_entity_counts: dict = {}
    for ln in lines:
        pass  # we'll fill this from the parser

    # ── Extract segments via ezdxf ────────────────────
    segments, entity_counts, ezdxf_warnings = _collect_segments_ezdxf(file_bytes)
    result.warnings.extend(ezdxf_warnings)
    result.entity_counts = entity_counts

    has_ole     = entity_counts.get("OLE2FRAME", 0) > 0
    geo_types   = {"LINE","LWPOLYLINE","POLYLINE","ARC","CIRCLE","SPLINE"}
    geo_count   = sum(entity_counts.get(t,0) for t in geo_types)
    total_ents  = sum(v for k,v in entity_counts.items() if not k.startswith("_"))

    # Diagnostics block
    result.diagnostics = {
        "total_entities":       total_ents,
        "geometric_entities":   geo_count,
        "ole2frame_count":      entity_counts.get("OLE2FRAME", 0),
        "insert_count":         entity_counts.get("_inserts", 0),
        "line_count":           entity_counts.get("LINE", 0),
        "lwpolyline_count":     entity_counts.get("LWPOLYLINE", 0),
        "polyline_count":       entity_counts.get("POLYLINE", 0),
        "arc_count":            entity_counts.get("ARC", 0),
        "circle_count":         entity_counts.get("CIRCLE", 0),
        "spline_count":         entity_counts.get("SPLINE", 0),
        "segments_extracted":   len(segments),
        "insunits_value":       insunits,
        "scale_factor":         sf,
    }

    # ── OLE-only file handling ────────────────────────
    if has_ole and geo_count == 0:
        result.warnings.append(
            "⚠ DXF contains an embedded OLE object (OLE2FRAME) but NO directly accessible "
            "vector geometry was found. This usually means the drawing was saved as an "
            "'OLE container' rather than a standard DXF. To fix: open in AutoCAD → "
            "EXPLODE the OLE frame → Save As DXF 2010 ASCII. Area cannot be calculated."
        )
        # Fall back to raw text parser
        ent_lines = _extract_entities_section(lines)
        segments, raw_counts, raw_warnings = _collect_segments_raw(ent_lines)
        result.warnings.extend(raw_warnings)
        for k, v in raw_counts.items():
            result.entity_counts[k] = result.entity_counts.get(k, 0) + v
        result.diagnostics["segments_extracted_fallback"] = len(segments)
        result.diagnostics["geometric_entities_fallback"] = sum(
            raw_counts.get(t, 0) for t in geo_types)

        if not segments:
            result.warnings.append(
                "No geometry found even after fallback parsing. "
                "The file appears to contain only an embedded OLE object."
            )
            return result

    if not segments:
        result.warnings.append(
            "No geometric segments found in DXF. "
            "Ensure the DXF file contains standard vector geometry (not just images/OLE)."
        )
        return result

    # ── Compute drawing extents ───────────────────────
    mn_x, mn_y, mx_x, mx_y, ext_w, ext_h = _all_segments_bounds(segments)
    result.diagnostics["drawing_extents"] = {
        "min_x": round(mn_x, 3), "min_y": round(mn_y, 3),
        "max_x": round(mx_x, 3), "max_y": round(mx_y, 3),
        "width_drawing_units":  round(ext_w, 3),
        "height_drawing_units": round(ext_h, 3),
        "width_m":  round(ext_w * sf, 3),
        "height_m": round(ext_h * sf, 3),
    }

    # ── Adaptive snap tolerance ───────────────────────
    # Typical AutoCAD drawings have gaps of 0.1–5mm
    # If in mm: tol=5 drawing units; if in m: tol=0.005
    tol = max(0.1, min(ext_w, ext_h) * 0.0005)  # 0.05% of smaller dimension
    result.diagnostics["snap_tolerance_drawing_units"] = round(tol, 6)

    # ── Build closed loops ────────────────────────────
    loops = _build_loops(segments, tol=tol)
    result.diagnostics["closed_loops_found"] = len(loops)

    if not loops:
        # No closed loops — try with larger tolerance
        tol2 = tol * 10
        loops = _build_loops(segments, tol=tol2)
        result.diagnostics["closed_loops_found_tol2"] = len(loops)
        if loops:
            result.warnings.append(
                f"No loops found at tight tolerance ({tol:.4f}). "
                f"Used relaxed tolerance ({tol2:.4f}) — {len(loops)} loop(s) found. "
                "This may indicate small gaps in the drawing."
            )

    all_bounds = (mn_x, mn_y, mx_x, mx_y, ext_w, ext_h)

    # ── Score all loops ───────────────────────────────
    candidates = []
    for loop in loops:
        area_raw = _shoelace(loop)
        if area_raw < 1e-6:
            continue

        area_m2  = area_raw * sf * sf
        area_ft2 = area_m2 * M2_TO_FT2

        lb       = _loop_bounds(loop)
        perim_raw = sum(_dist(loop[k], loop[(k+1)%len(loop)]) for k in range(len(loop)))
        perim_m  = perim_raw * sf
        perim_ft = perim_m * M_TO_FT

        is_sheet = _is_sheet_border(loop, all_bounds, sf)
        score    = _score_loop_as_building(loop, area_raw, sf)

        # Minimum area filter: must be at least 1 m² to be a building floor
        if area_m2 < 1.0:
            continue

        candidates.append({
            "area_raw":       area_raw,
            "area_m2":        round(area_m2,  3),
            "area_ft2":       round(area_ft2, 3),
            "perimeter_m":    round(perim_m,  3),
            "perimeter_ft":   round(perim_ft, 3),
            "width_m":        round(lb[4] * sf, 3),
            "height_m":       round(lb[5] * sf, 3),
            "is_sheet_border": is_sheet,
            "score":          score,
            "pts_count":      len(loop),
            "loop":           loop,  # kept for BOQ apply
        })

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Expose top candidates (without raw loop data)
    result.boundary_candidates = [
        {k: v for k, v in c.items() if k != "loop"}
        for c in candidates[:10]
    ]

    # ── Select building footprint ─────────────────────
    # Best candidate = highest score that is NOT a sheet border
    building_candidate = None
    for c in candidates:
        if not c["is_sheet_border"]:
            building_candidate = c
            break

    if building_candidate is None and candidates:
        # All were classified as sheet border — pick the largest anyway and warn
        building_candidate = candidates[0]
        result.warnings.append(
            "All detected boundaries were classified as possible sheet borders. "
            "Using the largest boundary. Please verify the result visually."
        )

    if building_candidate:
        result.building_footprint_area_m2  = building_candidate["area_m2"]
        result.building_footprint_area_ft2 = building_candidate["area_ft2"]
        result.boundary_perimeter_m        = building_candidate["perimeter_m"]
        result.boundary_perimeter_ft       = building_candidate["perimeter_ft"]
        result.slab_area_m2                = building_candidate["area_m2"]
        result.total_floor_area_m2         = building_candidate["area_m2"]
        result.diagnostics["selected_boundary"] = {
            "area_m2":    building_candidate["area_m2"],
            "area_ft2":   building_candidate["area_ft2"],
            "perimeter_m": building_candidate["perimeter_m"],
            "width_m":    building_candidate["width_m"],
            "height_m":   building_candidate["height_m"],
            "score":      round(building_candidate["score"], 2),
        }
    else:
        result.warnings.append(
            "No valid building boundary found (all loops either too small or no loops detected). "
            "Check that your DXF file contains closed polylines or connected line chains."
        )

    # ── Room areas ────────────────────────────────────
    # All candidates with area between 1 m² and 90% of building area are "rooms"
    bfa = result.building_footprint_area_m2
    for i, c in enumerate(candidates[1:], 1):
        if not c["is_sheet_border"] and c["area_m2"] < bfa * 0.9 and c["area_m2"] > 0.5:
            result.rooms.append({
                "name":    f"Area {i}",
                "area_m2": c["area_m2"],
                "area_ft2": c["area_ft2"],
            })
        if len(result.rooms) >= 20:
            break

    # ── Wall lengths ──────────────────────────────────
    walls = _extract_wall_lengths(segments, sf)
    result.external_wall_length_m = walls["external_m"]
    result.internal_wall_length_m = walls["internal_m"]
    result.total_wall_length_m    = walls["total_m"] if walls["total_m"] > 0 else walls["all_lines_m"]
    result.diagnostics["wall_extraction"] = walls

    # ── Doors / Windows ───────────────────────────────
    result.num_doors   = entity_counts.get("_doors",   0)
    result.num_windows = entity_counts.get("_windows", 0)

    # ── Sanity checks ─────────────────────────────────
    if result.building_footprint_area_m2 == 0 and len(segments) > 0:
        result.warnings.append(
            f"⚠ Geometry found ({len(segments)} segments) but area = 0. "
            "This usually means no CLOSED boundaries were detected. "
            "Check: 1) Are polylines explicitly closed? 2) Do line endpoints connect? "
            "3) Try a different drawing unit."
        )

    if result.building_footprint_area_m2 > 0:
        w = result.diagnostics.get("selected_boundary",{}).get("width_m", 0)
        h = result.diagnostics.get("selected_boundary",{}).get("height_m", 0)
        if w > 0 and h > 0:
            # Sanity: building dimensions should be in range 1–500 m
            if w < 1 or h < 1:
                result.warnings.append(
                    f"⚠ Detected building dimensions seem very small: {w:.2f}m × {h:.2f}m. "
                    "If the drawing is in mm, select 'MM' as drawing units."
                )
            elif w > 500 or h > 500:
                result.warnings.append(
                    f"⚠ Detected building dimensions seem very large: {w:.0f}m × {h:.0f}m. "
                    "If the drawing is in mm but you selected 'm', try selecting 'MM'."
                )

    result.diagnostics["total_segments"] = len(segments)
    result.diagnostics["boundary_candidates_count"] = len(candidates)

    return result
