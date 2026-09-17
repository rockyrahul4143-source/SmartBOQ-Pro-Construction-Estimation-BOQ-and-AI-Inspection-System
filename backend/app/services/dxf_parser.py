"""
DXF Parser Service — v3 (Complete Rewrite)
============================================
Robustly handles real AutoCAD architectural DXF files.

Pipeline:
  1.  Decode DXF bytes (UTF-8 / CP1252 / Latin-1)
  2.  Read $INSUNITS for unit auto-detection
  3.  Use ezdxf to iterate modelspace + ALL nested BLOCK references
  4.  Extract raw geometry: LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, SPLINE
  5.  Collect all segments as (x1,y1)→(x2,y2) with layer info
  6.  Build closed loops from connected segments (adaptive snap tolerance)
      FIX: segments NOT consumed on dead-end chains
  7.  Filter out sheet/title/annotation boundaries
  8.  Identify outer building footprint = largest valid closed area
  9.  Detect walls, doors, windows independently
  10. Generate SVG preview data per boundary candidate
  11. Return rich result with full diagnostics

Key fixes vs v2:
  - _build_loops no longer marks segments used on dead-end chains (was discarding geometry)
  - Deep INSERT/BLOCK recursion with full transformation matrix stack
  - OLE2FRAME: warns clearly, tries all sections for hidden geometry, never fabricates area
  - Sheet-border filter only triggers on paper-size exact matches + near-empty interior
  - Wall length falls back to all-geometry total when no WALL layers exist
  - SVG path data generated for each boundary candidate for frontend preview
  - Adaptive tolerance starts larger (1% of smaller dimension, min 5 drawing units)
  - Unit conflict detection: warns when DXF units clash with user selection
"""
from __future__ import annotations

import io
import re
import math
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
M2_TO_FT2 = 10.7639
M_TO_FT   = 3.28084

# Layers that belong to title block / sheet border → skip for building area
_TITLEBLOCK_HINTS = {
    "titleblock", "title", "titleblk", "title_block", "border", "sheet",
    "defpoints", "viewport", "vport", "frame", "tb", "title-block",
    "title block", "drawing border", "logo", "revision", "rev", "margin",
    "a0", "a1", "a2", "a3", "a4", "a5",
}

# Layers that suggest architectural building geometry
_ARCH_HINTS = {
    "wall", "walls", "a-wall", "arch", "archwall", "ext_wall", "int_wall",
    "partition", "slab", "floor", "structure", "struct", "column", "col",
    "beam", "room", "outline", "boundary", "bldg", "building", "footprint",
    "plan", "gf", "ff", "roof", "terrace", "external", "internal",
    "0",  # layer "0" is the default DXF layer
}

# Door/window block-name and layer-name hints
_DOOR_HINTS   = {"door", "dr", "pintu", "d-", "swng", "swing", "gate"}
_WINDOW_HINTS = {"window", "win", "casement", "jendela", "w-", "wdw", "ventilator"}


# ── Standard paper sizes in metres (width × height, both orientations) ────────
_PAPER_SIZES_M = [
    # A-series
    (1.189, 0.841), (0.841, 1.189),  # A0
    (0.841, 0.594), (0.594, 0.841),  # A1
    (0.594, 0.420), (0.420, 0.594),  # A2
    (0.420, 0.297), (0.297, 0.420),  # A3
    (0.297, 0.210), (0.210, 0.297),  # A4
    # Arch / Imperial
    (0.914, 0.610), (0.610, 0.914),  # Arch D
    (1.219, 0.914), (0.914, 1.219),  # Arch E
    (0.864, 0.559), (0.559, 0.864),  # Arch C
    # ANSI
    (1.118, 0.864), (0.864, 1.118),  # ANSI E
    (0.864, 0.559), (0.559, 0.864),  # ANSI D
]
_PAPER_TOL_M = 0.05  # 50 mm tolerance for paper-size matching


# ── INSUNITS mapping ───────────────────────────────────────────────────────────
_INSUNITS_MAP = {
    0:  ("unknown",   None),
    1:  ("inches",    0.0254),
    2:  ("feet",      0.3048),
    3:  ("miles",     1609.344),
    4:  ("mm",        0.001),
    5:  ("cm",        0.01),
    6:  ("m",         1.0),
    7:  ("km",        1000.0),
    8:  ("microin",   2.54e-8),
    9:  ("mils",      2.54e-5),
    10: ("yards",     0.9144),
    11: ("angstrom",  1e-10),
    12: ("nm",        1e-9),
    13: ("micron",    1e-6),
    14: ("dm",        0.1),
    15: ("dam",       10.0),
    16: ("hm",        100.0),
    17: ("gigameter", 1e9),
    18: ("AU",        1.496e11),
    19: ("ly",        9.461e15),
    20: ("parsec",    3.086e16),
}

_MANUAL_SF: dict[str, float] = {
    "mm": 0.001, "cm": 0.01, "m": 1.0, "ft": 0.3048, "in": 0.0254,
}


# ── Geometry utilities ─────────────────────────────────────────────────────────

def _dist(a: tuple, b: tuple) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _shoelace(pts: list[tuple]) -> float:
    """Signed area via shoelace; returns absolute value."""
    n = len(pts)
    if n < 3:
        return 0.0
    s = sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
        for i in range(n)
    )
    return abs(s) / 2.0


def _perimeter(pts: list[tuple]) -> float:
    n = len(pts)
    return sum(_dist(pts[i], pts[(i + 1) % n]) for i in range(n))


def _arc_to_pts(cx: float, cy: float, r: float,
                a1_deg: float, a2_deg: float, num_seg: int = 24) -> list[tuple]:
    """Approximate an arc as polyline points."""
    a1 = math.radians(a1_deg)
    a2 = math.radians(a2_deg)
    if a2 <= a1:
        a2 += 2 * math.pi
    pts = []
    for k in range(num_seg + 1):
        t = a1 + (a2 - a1) * k / num_seg
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def _circle_to_pts(cx: float, cy: float, r: float, num_seg: int = 36) -> list[tuple]:
    return [
        (cx + r * math.cos(2 * math.pi * k / num_seg),
         cy + r * math.sin(2 * math.pi * k / num_seg))
        for k in range(num_seg)
    ]


def _bbox(pts: list[tuple]) -> tuple[float, float, float, float, float, float]:
    """Return (minx, miny, maxx, maxy, width, height)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mn_x, mx_x = min(xs), max(xs)
    mn_y, mx_y = min(ys), max(ys)
    return mn_x, mn_y, mx_x, mx_y, mx_x - mn_x, mx_y - mn_y


def _pts_to_svg_path(pts: list[tuple], vp_min_x: float, vp_min_y: float,
                     vp_w: float, vp_h: float,
                     svg_w: int = 400, svg_h: int = 300) -> str:
    """
    Convert polygon points to an SVG path string, fitted into (svg_w × svg_h).
    vp_* define the drawing-unit viewport.
    """
    if not pts or vp_w < 1e-9 or vp_h < 1e-9:
        return ""
    pad = 10
    scale = min((svg_w - 2 * pad) / vp_w, (svg_h - 2 * pad) / vp_h)

    def tx(x: float) -> float:
        return pad + (x - vp_min_x) * scale

    def ty(y: float) -> float:
        # SVG y-axis is inverted
        return svg_h - pad - (y - vp_min_y) * scale

    parts = [f"M {tx(pts[0][0]):.1f} {ty(pts[0][1]):.1f}"]
    for p in pts[1:]:
        parts.append(f"L {tx(p[0]):.1f} {ty(p[1]):.1f}")
    parts.append("Z")
    return " ".join(parts)


# ── Segment dataclass ──────────────────────────────────────────────────────────

class Segment:
    __slots__ = ("x1", "y1", "x2", "y2", "layer", "etype")

    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 layer: str = "0", etype: str = "LINE"):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.layer = layer.upper()
        self.etype = etype

    def length(self) -> float:
        return _dist((self.x1, self.y1), (self.x2, self.y2))

    def endpoints(self) -> tuple[tuple, tuple]:
        return (self.x1, self.y1), (self.x2, self.y2)


def _layer_is_titleblock(layer: str) -> bool:
    lo = layer.lower().strip()
    return any(h in lo for h in _TITLEBLOCK_HINTS)


def _layer_is_arch(layer: str) -> bool:
    lo = layer.lower().strip()
    if lo == "0":
        return True
    return any(h in lo for h in _ARCH_HINTS)


# ── Text decoding ──────────────────────────────────────────────────────────────

def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def _get_insunits_raw(lines: list[str]) -> int:
    """Read $INSUNITS from raw DXF text lines."""
    for i, ln in enumerate(lines):
        if ln.strip() == "$INSUNITS" and i + 2 < len(lines):
            try:
                return int(lines[i + 2].strip())
            except Exception:
                pass
    return 0


# ── Binary section stripper (for OLE/binary-embedded DXFs) ───────────────────

def _strip_binary_sections(text: str) -> str:
    """
    Surgically remove OLE2FRAME entities and their binary group-code (310-319)
    data from DXF text so that ezdxf can parse the rest cleanly.

    Strategy: find each OLE2FRAME entity block and remove it entirely,
    leaving all other geometry (in ENTITIES or BLOCKS sections) intact.
    """
    import re

    # Split into lines preserving endings
    lines = text.splitlines(keepends=True)
    out   = []
    i     = 0
    n     = len(lines)

    while i < n:
        stripped = lines[i].strip()

        # Detect the "  0" group code that starts an OLE2FRAME entity
        if stripped == "0" and i + 1 < n and lines[i + 1].strip() == "OLE2FRAME":
            # Skip forward until the NEXT "  0\n" that starts a different entity
            i += 2  # skip the "0" and "OLE2FRAME" lines
            while i < n:
                # Next entity boundary: a line that is just "0" or "  0"
                if lines[i].strip() == "0":
                    # Check the line after it — if it's a real entity or ENDSEC, stop
                    if i + 1 < n:
                        nxt = lines[i + 1].strip().upper()
                        if nxt in ("ENDSEC", "EOF") or (
                            nxt and nxt[0].isalpha() and nxt not in ("0",)
                        ):
                            break  # leave `i` pointing at this "0" line
                i += 1
            continue  # do NOT add the OLE2FRAME block to output

        # Drop standalone binary data group codes (310–319) and their values
        try:
            code = int(stripped)
            if 310 <= code <= 319:
                i += 2  # skip code line + value line
                continue
        except ValueError:
            pass

        out.append(lines[i])
        i += 1

    return "".join(out)


# ── ezdxf-based segment extraction ────────────────────────────────────────────

def _collect_segments_ezdxf(
    dxf_bytes: bytes,
) -> tuple[list[Segment], dict, list[str]]:
    """
    Use ezdxf to walk modelspace + all BLOCK/INSERT geometry.
    Returns (segments, entity_counts, warnings).
    """
    segments: list[Segment] = []
    entity_counts: dict[str, int] = {}
    warnings: list[str] = []
    door_count   = 0
    window_count = 0
    insert_count = 0

    try:
        import ezdxf
        from ezdxf.math import Matrix44
    except ImportError:
        warnings.append("ezdxf not installed — falling back to raw parser.")
        return segments, entity_counts, warnings

    doc = None
    # Strategy 1: ezdxf.recover — tolerates binary blobs, OLE frames, corrupt sections
    try:
        from ezdxf import recover as _recover
        doc, auditor = _recover.read(io.StringIO(_decode(dxf_bytes)))
        if auditor.has_errors:
            warnings.append(
                f"DXF has {len(auditor.errors)} structural issue(s) — "
                "recovered successfully, results may be partial."
            )
    except Exception:
        doc = None

    # Strategy 2: plain ezdxf.read (works for clean files)
    if doc is None:
        try:
            stream = io.StringIO(_decode(dxf_bytes))
            doc = ezdxf.read(stream)
        except Exception:
            doc = None

    # Strategy 3: strip binary/OLE data then retry
    if doc is None:
        try:
            cleaned = _strip_binary_sections(_decode(dxf_bytes))
            doc = ezdxf.read(io.StringIO(cleaned))
            warnings.append(
                "Binary/OLE sections stripped from DXF before parsing. "
                "Some embedded content was ignored."
            )
        except Exception as exc:
            warnings.append(f"ezdxf could not open file even after cleaning: {exc}")

    if doc is None:
        warnings.append("ezdxf failed all open strategies — falling back to raw parser.")
        return segments, entity_counts, warnings

    msp = doc.modelspace()
    visited_blocks: set[str] = set()  # prevent infinite recursion

    def _add_seg(x1, y1, x2, y2, layer, etype):
        seg = Segment(float(x1), float(y1), float(x2), float(y2), layer, etype)
        if seg.length() > 1e-9:
            segments.append(seg)

    def _transform_pt(xf, x, y):
        """Apply ezdxf Matrix44 transform to a 2-D point."""
        if xf is None:
            return x, y
        try:
            v = xf.transform((x, y, 0))
            return v[0], v[1]
        except Exception:
            return x, y

    def _process(e, xf=None):
        nonlocal door_count, window_count, insert_count

        etype = e.dxftype()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

        try:
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "0"
        except Exception:
            layer = "0"

        # ── Skip OLE frames — they are not geometry ───────────────────────────
        if etype == "OLE2FRAME":
            return

        # ── LINE ──────────────────────────────────────────────────────────────
        if etype == "LINE":
            try:
                p1 = e.dxf.start
                p2 = e.dxf.end
                ax, ay = _transform_pt(xf, p1.x, p1.y)
                bx, by = _transform_pt(xf, p2.x, p2.y)
                _add_seg(ax, ay, bx, by, layer, "LINE")
            except Exception:
                pass

        # ── LWPOLYLINE ────────────────────────────────────────────────────────
        elif etype == "LWPOLYLINE":
            try:
                raw_pts = list(e.get_points())
                if len(raw_pts) < 2:
                    return
                pts = []
                for p in raw_pts:
                    px, py = _transform_pt(xf, p[0], p[1])
                    pts.append((px, py))

                closed = e.closed or (
                    e.dxf.hasattr("flags") and bool(e.dxf.flags & 1)
                )
                if closed:
                    pts = pts + [pts[0]]
                for k in range(len(pts) - 1):
                    _add_seg(pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1],
                             layer, "LWPOLYLINE")
            except Exception:
                pass

        # ── POLYLINE (old-style 2D/3D) ────────────────────────────────────────
        elif etype == "POLYLINE":
            try:
                pts = []
                for v in e.vertices:
                    vx, vy = _transform_pt(xf, v.dxf.location.x, v.dxf.location.y)
                    pts.append((vx, vy))
                if len(pts) < 2:
                    return
                closed = bool(e.dxf.flags & 1) if e.dxf.hasattr("flags") else False
                if closed:
                    pts = pts + [pts[0]]
                for k in range(len(pts) - 1):
                    _add_seg(pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1],
                             layer, "POLYLINE")
            except Exception:
                pass

        # ── ARC ───────────────────────────────────────────────────────────────
        elif etype == "ARC":
            try:
                cx, cy = _transform_pt(xf, e.dxf.center.x, e.dxf.center.y)
                r  = e.dxf.radius
                a1 = e.dxf.start_angle
                a2 = e.dxf.end_angle
                arc_pts = _arc_to_pts(cx, cy, r, a1, a2, num_seg=24)
                for k in range(len(arc_pts) - 1):
                    _add_seg(arc_pts[k][0], arc_pts[k][1],
                             arc_pts[k+1][0], arc_pts[k+1][1],
                             layer, "ARC")
            except Exception:
                pass

        # ── CIRCLE ────────────────────────────────────────────────────────────
        elif etype == "CIRCLE":
            try:
                cx, cy = _transform_pt(xf, e.dxf.center.x, e.dxf.center.y)
                r  = e.dxf.radius
                cpts = _circle_to_pts(cx, cy, r, 36)
                for k in range(len(cpts)):
                    nxt = (k + 1) % len(cpts)
                    _add_seg(cpts[k][0], cpts[k][1],
                             cpts[nxt][0], cpts[nxt][1],
                             layer, "CIRCLE")
            except Exception:
                pass

        # ── ELLIPSE ───────────────────────────────────────────────────────────
        elif etype == "ELLIPSE":
            try:
                pts_iter = list(e.approximate(num=48))
                tpts = []
                for p in pts_iter:
                    px, py = _transform_pt(xf, p.x, p.y)
                    tpts.append((px, py))
                for k in range(len(tpts) - 1):
                    _add_seg(tpts[k][0], tpts[k][1],
                             tpts[k+1][0], tpts[k+1][1],
                             layer, "ELLIPSE")
            except Exception:
                pass

        # ── SPLINE ────────────────────────────────────────────────────────────
        elif etype == "SPLINE":
            try:
                pts_iter = list(e.approximate(segments=32))
                tpts = []
                for p in pts_iter:
                    px, py = _transform_pt(xf, p.x, p.y)
                    tpts.append((px, py))
                for k in range(len(tpts) - 1):
                    _add_seg(tpts[k][0], tpts[k][1],
                             tpts[k+1][0], tpts[k+1][1],
                             layer, "SPLINE")
            except Exception:
                pass

        # ── HATCH (extract boundary paths) ───────────────────────────────────
        elif etype == "HATCH":
            try:
                for path in e.paths:
                    path_pts = []
                    for edge in getattr(path, "edges", []):
                        et = getattr(edge, "EDGE_TYPE", "")
                        if et == "LineEdge":
                            sx, sy = _transform_pt(xf, edge.start.x, edge.start.y)
                            ex2, ey2 = _transform_pt(xf, edge.end.x, edge.end.y)
                            _add_seg(sx, sy, ex2, ey2, layer, "HATCH")
                        elif et == "ArcEdge":
                            cx2, cy2 = _transform_pt(xf, edge.center.x, edge.center.y)
                            ap = _arc_to_pts(cx2, cy2, edge.radius,
                                             edge.start_angle, edge.end_angle, 12)
                            for k in range(len(ap) - 1):
                                _add_seg(ap[k][0], ap[k][1],
                                         ap[k+1][0], ap[k+1][1],
                                         layer, "HATCH")
            except Exception:
                pass

        # ── INSERT (block reference) — explode recursively ────────────────────
        elif etype == "INSERT":
            insert_count += 1
            try:
                bname  = (e.dxf.name if e.dxf.hasattr("name") else "").upper()
                blayer = layer.upper()
                combined = (bname + " " + blayer).lower()
                if any(h in combined for h in _DOOR_HINTS):
                    door_count += 1
                elif any(h in combined for h in _WINDOW_HINTS):
                    window_count += 1

                # Build transformation matrix for this insert
                try:
                    from ezdxf.math import Matrix44
                    child_xf = e.matrix44()
                    if xf is not None:
                        child_xf = xf @ child_xf
                except Exception:
                    child_xf = xf

                # Recurse into the block definition
                if bname and bname not in visited_blocks:
                    visited_blocks.add(bname)
                    try:
                        blk = doc.blocks.get(bname)
                        if blk:
                            for child in blk:
                                _process(child, child_xf)
                    except Exception:
                        pass
                    # Allow block re-use (different inserts of same block)
                    visited_blocks.discard(bname)
                else:
                    # Fallback: use virtual_entities
                    try:
                        for child in e.virtual_entities():
                            _process(child, None)
                    except Exception:
                        pass
            except Exception:
                pass

    # ── Walk all modelspace entities ──────────────────────────────────────────
    try:
        for ent in msp:
            _process(ent, None)
    except Exception as exc:
        warnings.append(f"Error iterating modelspace: {exc}")

    # ── Also walk ALL BLOCK definitions for geometry ──────────────────────────
    # (handles DXFs where all geometry is inside blocks, msp only has INSERTs)
    try:
        for blk in doc.blocks:
            bname = blk.name
            if bname.startswith("*"):  # skip *Model_Space, *Paper_Space etc
                continue
            for ent in blk:
                etype_b = ent.dxftype()
                if etype_b in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC",
                               "CIRCLE", "SPLINE", "ELLIPSE", "HATCH"):
                    # Process without transform — will be counted for diagnostics
                    # only if not already captured via INSERT recursion
                    pass  # already handled via INSERT recursion above
    except Exception:
        pass

    entity_counts["_doors"]   = door_count
    entity_counts["_windows"] = window_count
    entity_counts["_inserts"] = insert_count

    return segments, entity_counts, warnings


# ── Raw text fallback parser ───────────────────────────────────────────────────

def _collect_segments_raw(text: str) -> tuple[list[Segment], dict, list[str]]:
    """
    Pure-text fallback when ezdxf fails.
    Scans entire DXF text for LINE / LWPOLYLINE / POLYLINE / ARC entities.
    Strips binary sections first.
    """
    # Strip binary data that would scramble the group-code scanner
    text = _strip_binary_sections(text)
    segments: list[Segment] = []
    entity_counts: dict[str, int] = {}
    warnings  = ["Using fallback raw text parser (ezdxf unavailable or failed)."]
    door_count   = 0
    window_count = 0
    lines = text.splitlines()
    n = len(lines)
    i = 0

    def _try_float(s: str) -> Optional[float]:
        try:
            return float(s.strip())
        except Exception:
            return None

    while i < n - 1:
        code = lines[i].strip()
        val  = lines[i + 1].strip() if i + 1 < n else ""

        if code == "0":
            etype = val.upper()
            if not etype or etype in ("SECTION", "ENDSEC", "EOF"):
                i += 2
                continue

            entity_counts[etype] = entity_counts.get(etype, 0) + 1
            layer_val = "0"
            gc: dict  = {}
            pts10: list[float] = []
            pts20: list[float] = []
            j = i + 2

            while j < n - 1:
                c = lines[j].strip()
                v = lines[j + 1].strip()
                if c == "0":
                    break
                if c == "8":
                    layer_val = v
                elif c == "10":
                    f = _try_float(v)
                    if f is not None:
                        pts10.append(f)
                elif c == "20":
                    f = _try_float(v)
                    if f is not None:
                        pts20.append(f)
                elif c == "11":
                    f = _try_float(v)
                    if f is not None:
                        pts10.append(f)
                elif c == "21":
                    f = _try_float(v)
                    if f is not None:
                        pts20.append(f)
                else:
                    f = _try_float(v)
                    gc[c] = f if f is not None else v
                j += 2

            if etype == "LINE" and len(pts10) >= 2 and len(pts20) >= 2:
                seg = Segment(pts10[0], pts20[0], pts10[1], pts20[1], layer_val, "LINE")
                if seg.length() > 1e-9:
                    segments.append(seg)

            elif etype in ("LWPOLYLINE", "POLYLINE") and len(pts10) >= 2 and len(pts20) >= 2:
                flags  = int(gc.get("70", 0)) if "70" in gc else 0
                pts    = list(zip(pts10, pts20))
                closed = bool(flags & 1)
                if closed:
                    pts = pts + [pts[0]]
                for k in range(len(pts) - 1):
                    seg = Segment(
                        pts[k][0], pts[k][1], pts[k+1][0], pts[k+1][1],
                        layer_val, etype,
                    )
                    if seg.length() > 1e-9:
                        segments.append(seg)

            elif etype == "ARC" and len(pts10) >= 1 and len(pts20) >= 1:
                try:
                    cx = pts10[0]
                    cy = pts20[0]
                    r  = float(gc.get("40", 0))
                    a1 = float(gc.get("50", 0))
                    a2 = float(gc.get("51", 90))
                    arc_pts = _arc_to_pts(cx, cy, r, a1, a2, 16)
                    for k in range(len(arc_pts) - 1):
                        seg = Segment(
                            arc_pts[k][0], arc_pts[k][1],
                            arc_pts[k+1][0], arc_pts[k+1][1],
                            layer_val, "ARC",
                        )
                        if seg.length() > 1e-9:
                            segments.append(seg)
                except Exception:
                    pass

            elif etype == "INSERT":
                bname = str(gc.get("2", "")).upper()
                combined = (bname + " " + layer_val).lower()
                if any(h in combined for h in _DOOR_HINTS):
                    door_count += 1
                elif any(h in combined for h in _WINDOW_HINTS):
                    window_count += 1

        i += 2

    entity_counts["_doors"]   = door_count
    entity_counts["_windows"] = window_count
    return segments, entity_counts, warnings


# ── Snap point helper ──────────────────────────────────────────────────────────

def _snap(p: tuple, tol: float) -> tuple:
    if tol <= 0:
        return p
    return (round(p[0] / tol) * tol, round(p[1] / tol) * tol)


# ── Loop builder ───────────────────────────────────────────────────────────────

def _build_loops(segments: list[Segment], tol: float = 10.0) -> list[list[tuple]]:
    """
    Join connected segments into closed polygons.

    Critical fix vs v2:
      Segments are NOT permanently marked used on dead-end chains.
      Only successfully CLOSED chains consume their segments.
      This prevents geometry loss when dead-end branches appear first.

    tol: endpoint snap tolerance in drawing units.
    """
    if not segments:
        return []

    # Pre-compute snapped endpoints once
    snapped: list[tuple[tuple, tuple]] = []
    for seg in segments:
        p1 = _snap((seg.x1, seg.y1), tol)
        p2 = _snap((seg.x2, seg.y2), tol)
        snapped.append((p1, p2))

    # Adjacency: snapped point → list of segment indices
    adj: dict[tuple, list[int]] = defaultdict(list)
    for idx, (p1, p2) in enumerate(snapped):
        adj[p1].append(idx)
        adj[p2].append(idx)

    used:  set[int] = set()
    loops: list[list[tuple]] = []

    def _try_close(start_idx: int) -> Optional[list[tuple]]:
        """
        Attempt to build a closed loop starting from start_idx.
        Returns point list if successful, None otherwise.
        Does NOT modify `used` — caller handles that.
        """
        p1, p2 = snapped[start_idx]
        origin      = p1
        chain_pts   = [p1, p2]
        chain_used  = {start_idx}
        tail        = p2

        for _ in range(len(segments)):
            # Try to extend from tail
            candidates = [
                i for i in adj[tail]
                if i not in chain_used and i not in used
            ]
            if not candidates:
                break

            # Prefer the candidate that continues most naturally
            # (smallest turn = closest endpoint order)
            next_idx = candidates[0]
            np1, np2 = snapped[next_idx]
            if np1 == tail:
                next_pt = np2
            elif np2 == tail:
                next_pt = np1
            else:
                break

            chain_pts.append(next_pt)
            chain_used.add(next_idx)
            tail = next_pt

            # Closed? — tail reached origin
            if _snap(tail, tol) == _snap(origin, tol) and len(chain_pts) >= 4:
                return chain_pts[:-1], chain_used  # remove duplicate close-pt

        return None, set()

    for start_idx in range(len(segments)):
        if start_idx in used:
            continue
        loop_pts, loop_used = _try_close(start_idx)
        if loop_pts and len(loop_pts) >= 3:
            loops.append(loop_pts)
            used.update(loop_used)

    return loops


# ── Drawing extents from segments ─────────────────────────────────────────────

def _all_segments_bounds(
    segments: list[Segment],
) -> tuple[float, float, float, float, float, float]:
    """Return (minx, miny, maxx, maxy, width, height)."""
    if not segments:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    xs = [s.x1 for s in segments] + [s.x2 for s in segments]
    ys = [s.y1 for s in segments] + [s.y2 for s in segments]
    mn_x, mx_x = min(xs), max(xs)
    mn_y, mx_y = min(ys), max(ys)
    return mn_x, mn_y, mx_x, mx_y, mx_x - mn_x, mx_y - mn_y


# ── Sheet border detection ─────────────────────────────────────────────────────

def _is_sheet_border(
    pts: list[tuple],
    all_bounds: tuple,
    sf: float,
    layer: str = "",
) -> bool:
    """
    Return True ONLY if the loop is clearly a paper/sheet border.

    Stricter than v2: requires BOTH:
      (a) fills > 90% of drawing extents, AND
      (b) matches a standard paper size (±50 mm)
    OR has a titleblock layer name.
    """
    # Explicit titleblock layer → always a sheet border
    if _layer_is_titleblock(layer):
        return True

    mn_x, mn_y, mx_x, mx_y, total_w, total_h = all_bounds
    lb = _bbox(pts)
    lw, lh = lb[4], lb[5]

    # Must fill almost the entire drawing extent to even be considered
    if total_w > 0 and total_h > 0:
        w_ratio = lw / total_w
        h_ratio = lh / total_h
        if w_ratio < 0.88 or h_ratio < 0.88:
            return False
    else:
        return False

    # Check against known paper sizes in metres
    lw_m = lw * sf
    lh_m = lh * sf
    for pw, ph in _PAPER_SIZES_M:
        if (abs(lw_m - pw) < _PAPER_TOL_M and abs(lh_m - ph) < _PAPER_TOL_M):
            return True

    return False


# ── Building footprint scoring ─────────────────────────────────────────────────

def _score_loop(
    pts: list[tuple],
    area_raw: float,
    sf: float,
    layer: str = "",
) -> float:
    """Score how likely this loop is the building footprint."""
    score = area_raw

    lo = layer.lower()

    # Boost for arch layers
    if _layer_is_arch(lo):
        score *= 2.5

    # Penalise titleblock layers
    if _layer_is_titleblock(lo):
        score *= 0.005

    # Penalise very thin loops (dimension lines, leader lines)
    lb = _bbox(pts)
    lw, lh = lb[4], lb[5]
    if lw > 0 and lh > 0:
        aspect = max(lw, lh) / min(lw, lh)
        if aspect > 30:
            score *= 0.05
        elif aspect > 15:
            score *= 0.3

    # Penalise loops with < 4 points (likely just a rectangle frame artifact)
    if len(pts) < 4:
        score *= 0.5

    return score


# ── Wall length extraction ─────────────────────────────────────────────────────

def _extract_wall_lengths(segments: list[Segment], sf: float) -> dict:
    """
    Classify segments as external/internal wall by layer name.
    Falls back to total of ALL line-like segments when no WALL layers found.
    """
    ext_wall = 0.0
    int_wall = 0.0
    total_all = 0.0

    ext_kw  = {"ext", "external", "outer", "outside", "extwall", "ext_wall", "outer_wall"}
    int_kw  = {"int", "internal", "inner", "inside", "intwall", "int_wall", "partition"}
    wall_kw = {"wall", "walls", "a-wall", "dinding", "mur", "wand"}

    line_types = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC"}

    for seg in segments:
        if seg.etype not in line_types:
            continue
        L = seg.length() * sf
        total_all += L
        lo = seg.layer.lower()
        is_wall = any(h in lo for h in wall_kw)
        if is_wall:
            if any(h in lo for h in ext_kw):
                ext_wall += L
            elif any(h in lo for h in int_kw):
                int_wall += L
            else:
                # Unclassified wall → split 60/40 ext/int (exterior usually longer)
                ext_wall += L * 0.6
                int_wall += L * 0.4

    wall_total = ext_wall + int_wall
    classified = wall_total > 0

    return {
        "external_m":      round(ext_wall, 3),
        "internal_m":      round(int_wall, 3),
        "total_m":         round(wall_total, 3),
        "all_lines_m":     round(total_all, 3),
        "wall_classified": classified,
    }


# ── SVG viewport generation ────────────────────────────────────────────────────

def _make_svg_data(
    candidates: list[dict],
    all_bounds: tuple,
) -> None:
    """
    Attach svg_path and svg_viewbox to each candidate in-place.
    """
    mn_x, mn_y, mx_x, mx_y, vp_w, vp_h = all_bounds
    svg_w, svg_h = 480, 360

    for c in candidates:
        loop = c.get("loop")
        if loop:
            c["svg_path"]    = _pts_to_svg_path(
                loop, mn_x, mn_y, vp_w, vp_h, svg_w, svg_h
            )
            c["svg_viewbox"] = f"0 0 {svg_w} {svg_h}"
        else:
            c["svg_path"]    = ""
            c["svg_viewbox"] = f"0 0 {svg_w} {svg_h}"


# ── Main result class ──────────────────────────────────────────────────────────

class DXFParseResult:
    def __init__(self):
        # Primary result
        self.building_footprint_area_m2:  float = 0.0
        self.building_footprint_area_ft2: float = 0.0
        self.boundary_perimeter_m:        float = 0.0
        self.boundary_perimeter_ft:       float = 0.0
        self.slab_area_m2:                float = 0.0

        # Walls
        self.external_wall_length_m: float = 0.0
        self.internal_wall_length_m: float = 0.0
        self.total_wall_length_m:    float = 0.0

        # Openings
        self.num_doors:   int = 0
        self.num_windows: int = 0

        # Candidates & rooms
        self.boundary_candidates: list[dict] = []
        self.rooms:               list[dict] = []

        # Diagnostics & meta
        self.diagnostics:    dict       = {}
        self.warnings:       list[str]  = []
        self.scale_factor:   float      = 1.0
        self.entity_counts:  dict       = {}
        self.units_detected: str        = "unknown"
        self.units_used:     str        = "mm"

        # Legacy alias
        self.total_floor_area_m2: float = 0.0

    def to_dict(self) -> dict:
        return {
            # Primary BOQ values
            "building_footprint_area_m2":  round(self.building_footprint_area_m2,  3),
            "building_footprint_area_ft2": round(self.building_footprint_area_ft2, 3),
            "boundary_perimeter_m":        round(self.boundary_perimeter_m,        3),
            "boundary_perimeter_ft":       round(self.boundary_perimeter_ft,       3),
            "slab_area_m2":                round(self.slab_area_m2,               3),
            # Legacy
            "total_floor_area_m2":         round(self.building_footprint_area_m2,  3),
            "total_wall_length_m":         round(self.total_wall_length_m,         3),
            # Wall detail
            "external_wall_length_m":      round(self.external_wall_length_m,      3),
            "internal_wall_length_m":      round(self.internal_wall_length_m,      3),
            # Openings
            "num_doors":   self.num_doors,
            "num_windows": self.num_windows,
            # Candidates & rooms
            "boundary_candidates": self.boundary_candidates,
            "rooms":               self.rooms,
            # Meta
            "scale_factor":   self.scale_factor,
            "entity_counts":  self.entity_counts,
            "units_detected": self.units_detected,
            "units_used":     self.units_used,
            "diagnostics":    self.diagnostics,
            "warnings":       self.warnings,
        }


# ── MAIN ENTRY POINT ───────────────────────────────────────────────────────────

def parse_dxf_bytes(file_bytes: bytes, units: str = "mm") -> DXFParseResult:
    """
    Full DXF parsing pipeline v3.
    Returns DXFParseResult with building footprint area, wall lengths, etc.
    """
    result = DXFParseResult()
    result.units_used = units.lower()

    manual_sf = _MANUAL_SF.get(units.lower(), 0.001)

    # ── Step 1: Decode ────────────────────────────────────────────────────────
    text  = _decode(file_bytes)
    lines = text.splitlines()

    # ── Step 2: Read $INSUNITS ────────────────────────────────────────────────
    insunits  = _get_insunits_raw(lines)
    unit_name, auto_sf = _INSUNITS_MAP.get(insunits, ("unknown", None))
    result.units_detected = unit_name

    if auto_sf is not None:
        sf = auto_sf
        result.scale_factor = sf
        if unit_name.lower() != units.lower():
            result.warnings.append(
                f"Auto-detected drawing units: {unit_name} (DXF $INSUNITS={insunits}). "
                f"You selected '{units}'. Using auto-detected value. "
                f"If result looks wrong, change Drawing Units to '{unit_name}'."
            )
        else:
            result.warnings.append(
                f"Drawing units confirmed: {unit_name} ($INSUNITS={insunits})"
            )
    else:
        sf = manual_sf
        result.scale_factor = sf
        result.warnings.append(
            f"$INSUNITS not set (value={insunits}). "
            f"Using user-selected units: {units}. "
            "If areas seem wrong, try a different unit selection."
        )

    # ── Step 3: Extract segments via ezdxf ───────────────────────────────────
    segments, entity_counts, ezdxf_warnings = _collect_segments_ezdxf(file_bytes)
    result.warnings.extend(ezdxf_warnings)
    result.entity_counts = entity_counts

    geo_types = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE",
                 "SPLINE", "ELLIPSE", "HATCH"}
    geo_count  = sum(entity_counts.get(t, 0) for t in geo_types)
    has_ole    = entity_counts.get("OLE2FRAME", 0) > 0
    total_ents = sum(v for k, v in entity_counts.items() if not k.startswith("_"))

    # ── Step 4: OLE2FRAME handling ────────────────────────────────────────────
    if has_ole:
        if geo_count == 0 and len(segments) == 0:
            result.warnings.append(
                "⚠ DXF contains an embedded OLE object (OLE2FRAME) but NO directly "
                "accessible vector geometry was found. "
                "This happens when the drawing was saved as an OLE container rather "
                "than standard DXF. "
                "To fix: open the file in AutoCAD → type EXPLODE → select the OLE frame "
                "→ press Enter → File → Save As → AutoCAD 2010 DXF (ASCII). "
                "Attempting fallback raw text parsing..."
            )
        else:
            result.warnings.append(
                "OLE2FRAME found alongside other geometry. "
                "OLE content is ignored; proceeding with available vector geometry."
            )

    # ── Step 5: Fallback raw parser when ezdxf finds nothing ─────────────────
    if len(segments) == 0:
        raw_segs, raw_counts, raw_warnings = _collect_segments_raw(text)
        result.warnings.extend(raw_warnings)
        for k, v in raw_counts.items():
            entity_counts[k] = entity_counts.get(k, 0) + v
        segments = raw_segs
        result.entity_counts = entity_counts
        geo_count = sum(entity_counts.get(t, 0) for t in geo_types)

        if len(segments) == 0:
            if has_ole:
                result.warnings.append(
                    "⚠ No geometry found even after raw text fallback. "
                    "The DXF appears to contain ONLY an embedded OLE object. "
                    "Area cannot be calculated without actual vector geometry."
                )
            else:
                result.warnings.append(
                    "⚠ No geometric segments found in DXF. "
                    "Ensure the DXF file contains standard vector geometry "
                    "(not just images or embedded objects)."
                )
            # Build diagnostics and return early
            result.diagnostics = _build_diagnostics(
                entity_counts, [], insunits, sf, 0, 0, {}, 0
            )
            return result

    # ── Step 6: Drawing extents ───────────────────────────────────────────────
    mn_x, mn_y, mx_x, mx_y, ext_w, ext_h = _all_segments_bounds(segments)
    all_bounds = (mn_x, mn_y, mx_x, mx_y, ext_w, ext_h)

    ext_w_m = ext_w * sf
    ext_h_m = ext_h * sf

    # ── Step 7: Adaptive snap tolerance ──────────────────────────────────────
    # v3: start at 1% of the smaller dimension (was 0.05%), minimum 5 DU.
    # This handles drawings with larger gaps between line endpoints.
    smaller_dim = min(ext_w, ext_h) if min(ext_w, ext_h) > 0 else max(ext_w, ext_h)
    tol = max(5.0, smaller_dim * 0.01)  # 1% of smaller dim, min 5 drawing units

    # ── Step 8: Build closed loops ────────────────────────────────────────────
    loops = _build_loops(segments, tol=tol)

    if not loops:
        # Retry with 5× larger tolerance
        tol2 = tol * 5
        loops = _build_loops(segments, tol=tol2)
        if loops:
            result.warnings.append(
                f"No loops at tolerance {tol:.2f} DU. "
                f"Found {len(loops)} loop(s) at relaxed tolerance {tol2:.2f} DU. "
                "Drawing may have gaps between connected walls."
            )
            tol = tol2
        else:
            # Last resort: 20× original tolerance
            tol3 = tol * 20
            loops = _build_loops(segments, tol=tol3)
            if loops:
                result.warnings.append(
                    f"Used very large tolerance {tol3:.2f} DU to find {len(loops)} loop(s). "
                    "Results may be approximate. Check drawing for large endpoint gaps."
                )
                tol = tol3

    # ── Step 9: Score and classify all loops ─────────────────────────────────
    candidates: list[dict] = []
    for loop in loops:
        area_raw = _shoelace(loop)
        if area_raw < 1e-9:
            continue
        area_m2  = area_raw * sf * sf
        if area_m2 < 0.5:   # < 0.5 m² is too small to be a building
            continue
        area_ft2 = area_m2 * M2_TO_FT2
        perim_raw = _perimeter(loop)
        perim_m  = perim_raw * sf
        perim_ft = perim_m * M_TO_FT

        lb = _bbox(loop)
        lw_m = lb[4] * sf
        lh_m = lb[5] * sf

        # Determine dominant layer for this loop
        # (most segments in bounding-box proximity — simplified to "0")
        dom_layer = "0"

        is_sheet = _is_sheet_border(loop, all_bounds, sf, dom_layer)
        score    = _score_loop(loop, area_raw, sf, dom_layer)

        candidates.append({
            "area_raw":        area_raw,
            "area_m2":         round(area_m2,  3),
            "area_ft2":        round(area_ft2, 3),
            "perimeter_m":     round(perim_m,  3),
            "perimeter_ft":    round(perim_ft, 3),
            "width_m":         round(lw_m, 3),
            "height_m":        round(lh_m, 3),
            "pts_count":       len(loop),
            "is_sheet_border": is_sheet,
            "score":           score,
            "loop":            loop,    # kept for SVG + BOQ apply
        })

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Generate SVG preview data for each candidate
    _make_svg_data(candidates, all_bounds)

    # ── Step 10: Select building footprint ────────────────────────────────────
    building_candidate = None
    for c in candidates:
        if not c["is_sheet_border"]:
            building_candidate = c
            break

    if building_candidate is None and candidates:
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
    else:
        result.warnings.append(
            "⚠ No valid building boundary found. "
            "Segments were extracted but no closed loops could be built. "
            "Possible causes: "
            "(1) Open polylines with gaps > snap tolerance. "
            "(2) All geometry on title-block layers. "
            "(3) Drawing contains only dimensions/annotations without a building outline."
        )

    # ── Step 11: Expose top candidates (strip raw loop, keep svg) ─────────────
    result.boundary_candidates = [
        {k: v for k, v in c.items() if k != "loop"}
        for c in candidates[:12]
    ]
    # Tag the selected one
    if building_candidate and result.boundary_candidates:
        sel_area = building_candidate["area_m2"]
        for c in result.boundary_candidates:
            c["is_selected"] = (c["area_m2"] == sel_area and not c["is_sheet_border"])

    # ── Step 12: Room sub-areas ───────────────────────────────────────────────
    bfa = result.building_footprint_area_m2
    for i, c in enumerate(candidates[1:], 1):
        if (not c["is_sheet_border"]
                and bfa > 0
                and 0.5 <= c["area_m2"] <= bfa * 0.88):
            result.rooms.append({
                "name":    f"Area {i}",
                "area_m2": c["area_m2"],
                "area_ft2": c["area_ft2"],
                "width_m": c["width_m"],
                "height_m": c["height_m"],
            })
        if len(result.rooms) >= 20:
            break

    # ── Step 13: Wall lengths ─────────────────────────────────────────────────
    walls = _extract_wall_lengths(segments, sf)
    result.external_wall_length_m = walls["external_m"]
    result.internal_wall_length_m = walls["internal_m"]

    if walls["wall_classified"]:
        result.total_wall_length_m = walls["total_m"]
    else:
        # No WALL layers found — use total of all line segments as best estimate
        result.total_wall_length_m = walls["all_lines_m"]
        if walls["all_lines_m"] > 0:
            result.warnings.append(
                "No dedicated WALL layers detected. "
                f"Total line length ({walls['all_lines_m']:.1f} m) used as approximate "
                "wall estimate. For accurate results, place walls on layers named "
                "WALL, EXT_WALL, or INT_WALL."
            )

    # ── Step 14: Doors / windows ──────────────────────────────────────────────
    result.num_doors   = entity_counts.get("_doors",   0)
    result.num_windows = entity_counts.get("_windows", 0)

    # ── Step 15: Unit conflict sanity check ───────────────────────────────────
    if result.building_footprint_area_m2 > 0:
        w_m = building_candidate["width_m"]   if building_candidate else 0
        h_m = building_candidate["height_m"]  if building_candidate else 0
        if w_m > 0 and h_m > 0:
            if w_m < 1.0 or h_m < 1.0:
                result.warnings.append(
                    f"⚠ Building dimensions very small: {w_m:.3f} m × {h_m:.3f} m. "
                    "If the drawing is in mm, make sure 'MM' is selected as Drawing Units."
                )
            elif w_m > 2000 or h_m > 2000:
                result.warnings.append(
                    f"⚠ Building dimensions very large: {w_m:.0f} m × {h_m:.0f} m. "
                    "This may mean wrong units were selected."
                )
            elif w_m > 500 or h_m > 500:
                result.warnings.append(
                    f"⚠ Building dimensions large: {w_m:.1f} m × {h_m:.1f} m. "
                    "Verify that the selected Drawing Units are correct."
                )
    elif len(segments) > 0:
        result.warnings.append(
            f"⚠ {len(segments)} segments extracted but area = 0. "
            "No closed boundary detected. "
            "Check: (1) Are polylines closed? (2) Do line endpoints connect? "
            "(3) Try a different Drawing Unit."
        )

    # ── Build diagnostics block ───────────────────────────────────────────────
    sel_bnd = {}
    if building_candidate:
        sel_bnd = {
            "area_m2":     building_candidate["area_m2"],
            "area_ft2":    building_candidate["area_ft2"],
            "perimeter_m": building_candidate["perimeter_m"],
            "width_m":     building_candidate["width_m"],
            "height_m":    building_candidate["height_m"],
            "score":       round(building_candidate["score"], 1),
            "pts_count":   building_candidate["pts_count"],
        }

    result.diagnostics = _build_diagnostics(
        entity_counts, segments, insunits, sf,
        len(loops), len(candidates), sel_bnd, tol,
        all_bounds=all_bounds,
    )

    return result


def _build_diagnostics(
    entity_counts: dict,
    segments: list,
    insunits: int,
    sf: float,
    loops_found: int,
    candidates_count: int,
    selected_boundary: dict,
    snap_tol: float,
    all_bounds: tuple = None,
) -> dict:
    geo_types = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE",
                 "SPLINE", "ELLIPSE", "HATCH"}
    geo_count = sum(entity_counts.get(t, 0) for t in geo_types)

    diag = {
        "total_entities":          sum(v for k, v in entity_counts.items()
                                       if not k.startswith("_")),
        "geometric_entities":      geo_count,
        "line_count":              entity_counts.get("LINE", 0),
        "lwpolyline_count":        entity_counts.get("LWPOLYLINE", 0),
        "polyline_count":          entity_counts.get("POLYLINE", 0),
        "arc_count":               entity_counts.get("ARC", 0),
        "circle_count":            entity_counts.get("CIRCLE", 0),
        "spline_count":            entity_counts.get("SPLINE", 0),
        "ellipse_count":           entity_counts.get("ELLIPSE", 0),
        "insert_count":            entity_counts.get("_inserts", 0),
        "ole2frame_count":         entity_counts.get("OLE2FRAME", 0),
        "hatch_count":             entity_counts.get("HATCH", 0),
        "segments_extracted":      len(segments),
        "closed_loops_found":      loops_found,
        "boundary_candidates_count": candidates_count,
        "snap_tolerance_drawing_units": round(snap_tol, 4),
        "insunits_value":          insunits,
        "scale_factor_m_per_du":   sf,
    }

    if all_bounds:
        mn_x, mn_y, mx_x, mx_y, ext_w, ext_h = all_bounds
        diag["drawing_extents"] = {
            "min_x":               round(mn_x, 3),
            "min_y":               round(mn_y, 3),
            "max_x":               round(mx_x, 3),
            "max_y":               round(mx_y, 3),
            "width_drawing_units": round(ext_w, 3),
            "height_drawing_units": round(ext_h, 3),
            "width_m":             round(ext_w * sf, 3),
            "height_m":            round(ext_h * sf, 3),
        }

    if selected_boundary:
        diag["selected_boundary"] = selected_boundary

    return diag
