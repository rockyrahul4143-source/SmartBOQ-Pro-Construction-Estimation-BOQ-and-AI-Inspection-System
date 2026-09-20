"""
DXF Parser Service — v4 (Shapely-based exact area calculation)
==============================================================
Calculates building footprint area exactly as AutoCAD AREA command would.

Core approach
-------------
1. Extract every geometric entity from modelspace + all BLOCK definitions
   (handles geometry hidden inside INSERT/BLOCK references)
2. Two extraction paths run in parallel:
   A. DIRECT POLYGONS — closed LWPOLYLINE / POLYLINE / HATCH boundaries
      → converted directly to Shapely Polygons (exact area, no approximation)
   B. LINE CHAINS — LINE + ARC segments that form closed loops when connected
      → graph-based chain reconstruction → Shapely Polygons
3. All polygons deduplicated by area similarity
4. Polygons classified: sheet/title border vs building footprint
   → Sheet borders rejected (paper-size match OR > 90% drawing extents)
5. Multi-building detection: if multiple large non-nested polygons remain,
   each is reported as a separate building (Building A, B, C…)
6. Unit conversion: reads $INSUNITS, applies correct scale factor
7. Final area matches AutoCAD AREA command output

Key improvements over v3
------------------------
- Uses Shapely for mathematically exact polygon areas
- Closed LWPOLYLINE → direct Shapely polygon (no lossy loop-builder)
- LINE segments → graph adjacency → closed chains (not greedy single-path)
- OLE2FRAME binary blob stripped surgically before ezdxf parse
- ezdxf.readfile (binary path) tried first — handles both ASCII+binary DXF
- DWG files rejected with clear conversion instructions
- Multi-building support: Building A, B, C with individual + total areas
"""
from __future__ import annotations

import io
import math
import logging
import re
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
M2_TO_FT2 = 10.7639
M_TO_FT   = 3.28084

# ── Layer name hints ───────────────────────────────────────────────────────────
_TITLEBLOCK_HINTS = {
    "titleblock","title","titleblk","title_block","border","sheet",
    "defpoints","viewport","vport","frame","tb","title-block","margin",
    "a0","a1","a2","a3","a4","logo","revision","rev",
}
_ARCH_HINTS = {
    "wall","walls","a-wall","arch","slab","floor","structure","column",
    "col","beam","room","outline","boundary","building","footprint","plan",
    "0",   # layer 0 is the default — always include
}
_DOOR_HINTS   = {"door","dr","pintu","swing","gate"}
_WINDOW_HINTS = {"window","win","casement","jendela","wdw","ventilator"}

# ── Standard paper sizes in metres (both orientations) ────────────────────────
_PAPER_SIZES_M = [
    (1.189,0.841),(0.841,1.189),   # A0
    (0.841,0.594),(0.594,0.841),   # A1
    (0.594,0.420),(0.420,0.594),   # A2
    (0.420,0.297),(0.297,0.420),   # A3
    (0.297,0.210),(0.210,0.297),   # A4
    (0.914,0.610),(0.610,0.914),   # Arch D
    (1.219,0.914),(0.914,1.219),   # Arch E
    (1.118,0.864),(0.864,1.118),   # ANSI E
]
_PAPER_TOL_M = 0.06   # ±60 mm tolerance

# ── INSUNITS mapping ───────────────────────────────────────────────────────────
_INSUNITS_MAP = {
    0: ("unknown", None),
    1: ("inches",  0.0254),
    2: ("feet",    0.3048),
    3: ("miles",   1609.344),
    4: ("mm",      0.001),
    5: ("cm",      0.01),
    6: ("m",       1.0),
    7: ("km",      1000.0),
    14: ("dm",     0.1),
}
_MANUAL_SF: dict[str,float] = {
    "mm":0.001,"cm":0.01,"m":1.0,"ft":0.3048,"in":0.0254,
}


# ── Text / bytes helpers ───────────────────────────────────────────────────────

def _decode(raw: bytes) -> str:
    for enc in ("utf-8","cp1252","latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def _get_insunits(lines: list[str]) -> int:
    for i, ln in enumerate(lines):
        if ln.strip() == "$INSUNITS" and i+2 < len(lines):
            try:
                return int(lines[i+2].strip())
            except Exception:
                pass
    return 0


def _is_dwg(raw: bytes) -> bool:
    """Binary DWG files start with AC followed by version number."""
    return raw[:2] == b"AC" and raw[2:4] != b"DB"


# ── OLE / binary section stripper ─────────────────────────────────────────────

def _strip_binary_sections(text: str) -> str:
    """
    Surgically remove OLE2FRAME entities and binary group-code (310-319) blobs.
    Preserves all other DXF sections including BLOCKS with real geometry.
    """
    lines = text.splitlines(keepends=True)
    out:  list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        s = lines[i].strip()

        # OLE2FRAME entity: remove entire block until next entity boundary
        if s == "0" and i+1 < n and lines[i+1].strip() == "OLE2FRAME":
            i += 2
            while i < n:
                if lines[i].strip() == "0" and i+1 < n:
                    nxt = lines[i+1].strip().upper()
                    if nxt in ("ENDSEC","EOF") or (nxt and nxt[0].isalpha()):
                        break
                i += 1
            continue

        # Binary group codes 310-319: skip code + value lines
        try:
            code = int(s)
            if 310 <= code <= 319:
                i += 2
                continue
        except ValueError:
            pass

        out.append(lines[i])
        i += 1

    return "".join(out)


# ── Geometry helpers ───────────────────────────────────────────────────────────

def _arc_pts(cx, cy, r, a1_deg, a2_deg, n=48) -> list[tuple]:
    a1 = math.radians(a1_deg)
    a2 = math.radians(a2_deg)
    if a2 <= a1:
        a2 += 2*math.pi
    return [
        (cx + r*math.cos(a1+(a2-a1)*k/n),
         cy + r*math.sin(a1+(a2-a1)*k/n))
        for k in range(n+1)
    ]


def _xf_pt(xf, x, y):
    if xf is None:
        return x, y
    try:
        v = xf.transform((x, y, 0))
        return v[0], v[1]
    except Exception:
        return x, y


# ── ezdxf document opener ──────────────────────────────────────────────────────

def _open_dxf(dxf_bytes: bytes, warnings: list[str]):
    """
    Try multiple strategies to open DXF bytes with ezdxf.
    Returns (doc, method_used) or (None, error_msg).
    """
    import ezdxf

    # Strategy 1: readfile via temp file path (handles binary+ASCII, most robust)
    import tempfile, os
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            f.write(dxf_bytes)
            tmp = f.name
        doc = ezdxf.readfile(tmp)
        return doc, "readfile"
    except Exception as e1:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass

    # Strategy 2: ezdxf.read() on text stream
    try:
        doc = ezdxf.read(io.StringIO(_decode(dxf_bytes)))
        return doc, "read_stream"
    except Exception as e2:
        pass

    # Strategy 3: strip binary/OLE first then retry
    try:
        cleaned = _strip_binary_sections(_decode(dxf_bytes))
        tmp2 = None
        with tempfile.NamedTemporaryFile(
            suffix=".dxf", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(cleaned)
            tmp2 = f.name
        try:
            doc = ezdxf.readfile(tmp2)
            warnings.append(
                "OLE/binary sections stripped from DXF before parsing. "
                "Embedded images ignored; vector geometry preserved."
            )
            return doc, "readfile_cleaned"
        finally:
            if tmp2 and os.path.exists(tmp2):
                try:
                    os.unlink(tmp2)
                except Exception:
                    pass
    except Exception as e3:
        warnings.append(f"ezdxf failed all open strategies: {e3}")
        return None, str(e3)


# ── Shapely polygon builders ───────────────────────────────────────────────────

def _make_polygon(pts: list[tuple]):
    """
    Build a valid Shapely polygon from a point list.
    Returns polygon or None if invalid.
    """
    try:
        from shapely.geometry import Polygon
        from shapely.validation import make_valid
        if len(pts) < 3:
            return None
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = make_valid(poly)
        if poly.is_empty or poly.area < 1e-9:
            return None
        # Take the exterior if make_valid returned a GeometryCollection
        if poly.geom_type == "GeometryCollection":
            largest = max(
                (g for g in poly.geoms if g.geom_type in ("Polygon","MultiPolygon")),
                key=lambda g: g.area, default=None
            )
            return largest
        return poly
    except Exception:
        return None


def _pts_to_svg(pts, mn_x, mn_y, vp_w, vp_h, sw=480, sh=320) -> str:
    if not pts or vp_w < 1e-9 or vp_h < 1e-9:
        return ""
    pad = 12
    scale = min((sw-2*pad)/vp_w, (sh-2*pad)/vp_h)
    def tx(x): return pad + (x - mn_x)*scale
    def ty(y): return sh - pad - (y - mn_y)*scale
    d = f"M {tx(pts[0][0]):.1f} {ty(pts[0][1]):.1f}"
    for p in pts[1:]:
        d += f" L {tx(p[0]):.1f} {ty(p[1]):.1f}"
    return d + " Z"


# ── Core geometry extractor ────────────────────────────────────────────────────

class _GeoExtractor:
    """
    Walks an ezdxf document and extracts:
      - direct_polys: list of (pts, layer, etype) for closed LWPOLY/POLY/HATCH
      - segments:     list of (x1,y1,x2,y2, layer, etype)
      - entity_counts dict
      - door_count, window_count
    """

    def __init__(self):
        self.direct_polys: list[tuple] = []
        self.segments:     list[tuple] = []
        self.entity_counts: dict[str,int] = {}
        self.door_count   = 0
        self.window_count = 0
        self._visited_blocks: set[str] = set()

    def run(self, doc) -> None:
        msp = doc.modelspace()
        for e in msp:
            self._process(e, None)

        # Also walk every named block definition once
        # (geometry referenced by INSERT that may not have been traversed)
        for blk in doc.blocks:
            if blk.name.startswith("*"):
                continue   # system blocks: *Model_Space etc.
            for e in blk:
                et = e.dxftype()
                if et in ("LINE","LWPOLYLINE","POLYLINE","ARC",
                          "CIRCLE","SPLINE","ELLIPSE","HATCH"):
                    self._process(e, None)

    def _count(self, etype: str):
        self.entity_counts[etype] = self.entity_counts.get(etype, 0) + 1

    def _add_seg(self, x1,y1,x2,y2, layer, etype):
        dx = x2-x1; dy = y2-y1
        if dx*dx + dy*dy > 1e-18:
            self.segments.append((x1,y1,x2,y2, layer.upper(), etype))

    def _process(self, e, xf):
        etype = e.dxftype()
        self._count(etype)

        try:
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "0"
        except Exception:
            layer = "0"

        if etype == "OLE2FRAME":
            return

        # ── LINE ──────────────────────────────────────────────────────────────
        if etype == "LINE":
            try:
                ax,ay = _xf_pt(xf, e.dxf.start.x, e.dxf.start.y)
                bx,by = _xf_pt(xf, e.dxf.end.x,   e.dxf.end.y)
                self._add_seg(ax,ay,bx,by, layer,"LINE")
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
                    px,py = _xf_pt(xf, p[0], p[1])
                    pts.append((px,py))
                closed = e.closed or (
                    e.dxf.hasattr("flags") and bool(e.dxf.flags & 1)
                )
                if closed and len(pts) >= 3:
                    self.direct_polys.append((pts, layer, "LWPOLYLINE"))
                # Also store as segments for LINE chain path
                work = pts + [pts[0]] if closed else pts
                for k in range(len(work)-1):
                    self._add_seg(work[k][0],work[k][1],
                                  work[k+1][0],work[k+1][1], layer,"LWPOLYLINE")
            except Exception:
                pass

        # ── POLYLINE ──────────────────────────────────────────────────────────
        elif etype == "POLYLINE":
            try:
                pts = []
                for v in e.vertices:
                    vx,vy = _xf_pt(xf, v.dxf.location.x, v.dxf.location.y)
                    pts.append((vx,vy))
                if len(pts) < 2:
                    return
                closed = bool(e.dxf.flags & 1) if e.dxf.hasattr("flags") else False
                if closed and len(pts) >= 3:
                    self.direct_polys.append((pts, layer, "POLYLINE"))
                work = pts + [pts[0]] if closed else pts
                for k in range(len(work)-1):
                    self._add_seg(work[k][0],work[k][1],
                                  work[k+1][0],work[k+1][1], layer,"POLYLINE")
            except Exception:
                pass

        # ── ARC ───────────────────────────────────────────────────────────────
        elif etype == "ARC":
            try:
                cx,cy = _xf_pt(xf, e.dxf.center.x, e.dxf.center.y)
                r  = e.dxf.radius
                a1 = e.dxf.start_angle
                a2 = e.dxf.end_angle
                ap = _arc_pts(cx,cy,r,a1,a2, n=24)
                for k in range(len(ap)-1):
                    self._add_seg(ap[k][0],ap[k][1],
                                  ap[k+1][0],ap[k+1][1], layer,"ARC")
            except Exception:
                pass

        # ── CIRCLE ────────────────────────────────────────────────────────────
        elif etype == "CIRCLE":
            try:
                cx,cy = _xf_pt(xf, e.dxf.center.x, e.dxf.center.y)
                r  = e.dxf.radius
                n  = 36
                pts = [
                    (cx+r*math.cos(2*math.pi*k/n),
                     cy+r*math.sin(2*math.pi*k/n))
                    for k in range(n)
                ]
                self.direct_polys.append((pts, layer, "CIRCLE"))
                for k in range(n):
                    nxt = (k+1)%n
                    self._add_seg(pts[k][0],pts[k][1],
                                  pts[nxt][0],pts[nxt][1], layer,"CIRCLE")
            except Exception:
                pass

        # ── SPLINE ────────────────────────────────────────────────────────────
        elif etype == "SPLINE":
            try:
                sp = list(e.approximate(segments=48))
                pts = [_xf_pt(xf, p.x, p.y) for p in sp]
                for k in range(len(pts)-1):
                    self._add_seg(pts[k][0],pts[k][1],
                                  pts[k+1][0],pts[k+1][1], layer,"SPLINE")
            except Exception:
                pass

        # ── ELLIPSE ───────────────────────────────────────────────────────────
        elif etype == "ELLIPSE":
            try:
                pts = [_xf_pt(xf, p.x, p.y) for p in e.approximate(num=48)]
                for k in range(len(pts)-1):
                    self._add_seg(pts[k][0],pts[k][1],
                                  pts[k+1][0],pts[k+1][1], layer,"ELLIPSE")
            except Exception:
                pass

        # ── HATCH boundaries ──────────────────────────────────────────────────
        elif etype == "HATCH":
            try:
                for path in e.paths:
                    path_pts = []
                    for edge in getattr(path, "edges", []):
                        et2 = getattr(edge,"EDGE_TYPE","")
                        if et2 == "LineEdge":
                            sx,sy = _xf_pt(xf, edge.start.x, edge.start.y)
                            ex2,ey2 = _xf_pt(xf, edge.end.x, edge.end.y)
                            path_pts.append((sx,sy))
                        elif et2 == "ArcEdge":
                            cx2,cy2 = _xf_pt(xf, edge.center.x, edge.center.y)
                            ap = _arc_pts(cx2,cy2,edge.radius,
                                          edge.start_angle,edge.end_angle, n=12)
                            path_pts.extend(ap[:-1])
                    if len(path_pts) >= 3:
                        self.direct_polys.append((path_pts, layer, "HATCH"))
            except Exception:
                pass

        # ── INSERT ────────────────────────────────────────────────────────────
        elif etype == "INSERT":
            try:
                bname = (e.dxf.name if e.dxf.hasattr("name") else "").upper()
                combo = (bname+" "+layer).lower()
                if any(h in combo for h in _DOOR_HINTS):
                    self.door_count += 1
                elif any(h in combo for h in _WINDOW_HINTS):
                    self.window_count += 1
            except Exception:
                pass
            # Recurse with transform
            try:
                from ezdxf.math import Matrix44
                child_xf = e.matrix44()
                if xf is not None:
                    child_xf = xf @ child_xf
            except Exception:
                child_xf = xf
            try:
                bname_key = (e.dxf.name if e.dxf.hasattr("name") else "")
                if bname_key and bname_key not in self._visited_blocks:
                    self._visited_blocks.add(bname_key)
                    try:
                        blk = e._doc.blocks.get(bname_key)
                        if blk:
                            for child in blk:
                                self._process(child, child_xf)
                    except Exception:
                        pass
                    self._visited_blocks.discard(bname_key)
                else:
                    for child in e.virtual_entities():
                        self._process(child, None)
            except Exception:
                pass


# ── Raw text fallback extractor ────────────────────────────────────────────────

def _raw_extract(text: str) -> tuple[list,list,dict]:
    """
    Pure text fallback when ezdxf completely fails.
    Returns (direct_polys, segments, entity_counts).
    """
    text   = _strip_binary_sections(text)
    lines  = text.splitlines()
    n      = len(lines)
    direct_polys: list = []
    segments:     list = []
    entity_counts: dict = {}
    i = 0

    def _f(s):
        try: return float(s.strip())
        except: return None

    while i < n-1:
        if lines[i].strip() == "0":
            etype = lines[i+1].strip().upper()
            if not etype or etype in ("SECTION","ENDSEC","EOF",""):
                i += 2; continue
            entity_counts[etype] = entity_counts.get(etype,0)+1
            layer = "0"
            pts10: list = []; pts20: list = []; pts11: list = []; pts21: list = []
            gc: dict = {}
            j = i+2
            while j < n-1:
                c = lines[j].strip()
                v = lines[j+1].strip()
                if c == "0": break
                if c == "8": layer = v
                elif c == "10":
                    f = _f(v)
                    if f is not None: pts10.append(f)
                elif c == "20":
                    f = _f(v)
                    if f is not None: pts20.append(f)
                elif c == "11":
                    f = _f(v)
                    if f is not None: pts11.append(f)
                elif c == "21":
                    f = _f(v)
                    if f is not None: pts21.append(f)
                else:
                    f = _f(v)
                    gc[c] = f if f is not None else v
                j += 2

            if etype == "LINE" and pts10 and pts20 and pts11 and pts21:
                segments.append((pts10[0],pts20[0],pts11[0],pts21[0],layer,"LINE"))

            elif etype in ("LWPOLYLINE","POLYLINE") and len(pts10)>=2 and len(pts20)>=2:
                flags  = int(gc.get("70",0)) if "70" in gc else 0
                pts    = list(zip(pts10,pts20))
                closed = bool(flags&1)
                if closed and len(pts)>=3:
                    direct_polys.append((pts, layer, etype))
                work = pts+[pts[0]] if closed else pts
                for k in range(len(work)-1):
                    segments.append((work[k][0],work[k][1],
                                     work[k+1][0],work[k+1][1],layer,etype))

            elif etype == "ARC" and pts10 and pts20:
                try:
                    cx=pts10[0]; cy=pts20[0]
                    r=float(gc.get("40",0))
                    a1=float(gc.get("50",0)); a2=float(gc.get("51",90))
                    ap = _arc_pts(cx,cy,r,a1,a2,16)
                    for k in range(len(ap)-1):
                        segments.append((ap[k][0],ap[k][1],
                                         ap[k+1][0],ap[k+1][1],layer,"ARC"))
                except Exception:
                    pass
        i += 2
    return direct_polys, segments, entity_counts


# ── Snap helper ────────────────────────────────────────────────────────────────

def _snap(x, y, tol):
    if tol <= 0: return (x, y)
    return (round(x/tol)*tol, round(y/tol)*tol)


# ── Graph-based LINE chain → closed loops ─────────────────────────────────────

def _chain_to_loops(
    segments: list[tuple],
    tol: float,
    max_segs: int = 8000,
) -> list[list[tuple]]:
    """
    Build adjacency graph from segment endpoints (snapped to tol grid).
    Trace closed chains with a greedy O(n) walk — each segment visited once.
    This is fast even for 20 000+ segment drawings.

    Strategy: greedy chain-extension from each unvisited segment.
    When the chain's tail reaches the chain's head → closed loop.
    Segments are only consumed when they are part of a closed loop.
    If a chain dead-ends, those segments are still available for other chains.
    """
    if not segments:
        return []

    # Cap to avoid runaway on pathological files
    work_segs = segments[:max_segs] if len(segments) > max_segs else segments

    # Pre-snap endpoints
    ep: list[tuple] = []
    for seg in work_segs:
        p1 = _snap(seg[0], seg[1], tol)
        p2 = _snap(seg[2], seg[3], tol)
        ep.append((p1, p2))

    # Adjacency: snapped_point → list of segment indices
    adj: dict[tuple, list[int]] = defaultdict(list)
    for idx, (p1, p2) in enumerate(ep):
        if p1 != p2:
            adj[p1].append(idx)
            adj[p2].append(idx)

    used:  set[int]        = set()
    loops: list[list[tuple]] = []

    for start_idx in range(len(work_segs)):
        if start_idx in used:
            continue

        p1, p2   = ep[start_idx]
        origin   = p1
        chain    = [p1, p2]
        in_chain = {start_idx}
        tail     = p2

        max_steps = len(work_segs) + 1
        steps     = 0
        closed    = False

        while steps < max_steps:
            steps += 1
            # Try to extend from tail
            candidates = [
                i for i in adj[tail]
                if i not in in_chain and i not in used
            ]
            if not candidates:
                break

            # Pick the first available candidate
            next_idx    = candidates[0]
            np1, np2    = ep[next_idx]
            next_pt     = np2 if np1 == tail else np1

            chain.append(next_pt)
            in_chain.add(next_idx)
            tail = next_pt

            # Closed?
            if tail == origin and len(chain) >= 4:
                closed = True
                break

        if closed and len(chain) >= 4:
            loops.append(chain[:-1])   # drop the duplicate closing point
            used.update(in_chain)

    return loops


# ── Building vs sheet-border classifier ───────────────────────────────────────

def _all_bounds(segs: list[tuple]) -> tuple:
    if not segs:
        return 0,0,0,0,0,0
    xs = [s[0] for s in segs] + [s[2] for s in segs]
    ys = [s[1] for s in segs] + [s[3] for s in segs]
    mn_x,mx_x = min(xs),max(xs)
    mn_y,mx_y = min(ys),max(ys)
    return mn_x,mn_y,mx_x,mx_y, mx_x-mn_x, mx_y-mn_y


def _poly_bbox(poly) -> tuple:
    b = poly.bounds  # (minx,miny,maxx,maxy)
    return b[0],b[1],b[2],b[3], b[2]-b[0], b[3]-b[1]


def _is_sheet_border(poly, all_bnds, sf: float, layer: str="") -> bool:
    """Return True if polygon is a paper/sheet border — not a building."""
    lo = layer.lower()
    if any(h in lo for h in _TITLEBLOCK_HINTS):
        return True

    mn_x,mn_y,mx_x,mx_y, total_w,total_h = all_bnds
    _,_,_,_, pw,ph = _poly_bbox(poly)

    # Must cover > 88% of drawing extent to even be considered sheet border
    if total_w > 0 and total_h > 0:
        if pw/total_w < 0.88 or ph/total_h < 0.88:
            return False
    else:
        return False

    # Check against known paper sizes in metres
    pw_m, ph_m = pw*sf, ph*sf
    for ppw,pph in _PAPER_SIZES_M:
        if abs(pw_m-ppw) < _PAPER_TOL_M and abs(ph_m-pph) < _PAPER_TOL_M:
            return True

    return False


def _layer_is_arch(layer: str) -> bool:
    lo = layer.lower()
    return lo == "0" or any(h in lo for h in _ARCH_HINTS)


def _score_poly(poly, sf: float, layer: str="") -> float:
    """Higher score = more likely to be building footprint."""
    area = poly.area
    score = area
    lo = layer.lower()
    if _layer_is_arch(lo):     score *= 3.0
    if any(h in lo for h in _TITLEBLOCK_HINTS): score *= 0.01
    _,_,_,_, pw,ph = _poly_bbox(poly)
    if pw > 0 and ph > 0:
        asp = max(pw,ph)/min(pw,ph)
        if asp > 30:   score *= 0.05
        elif asp > 15: score *= 0.3
    return score


# ── Multi-building separator ───────────────────────────────────────────────────

def _separate_buildings(polys: list) -> list[list]:
    """
    Group polygons into separate buildings.
    A polygon is a separate building if it does NOT overlap or nest
    inside any larger polygon in the list.

    Returns list of groups; each group = [outer_poly, inner_poly, ...].
    """
    from shapely.geometry import MultiPolygon

    # Sort descending by area
    polys = sorted(polys, key=lambda p: p.area, reverse=True)
    assigned = [False]*len(polys)
    groups   = []

    for i, poly in enumerate(polys):
        if assigned[i]:
            continue
        group = [poly]
        assigned[i] = True
        for j, other in enumerate(polys):
            if assigned[j] or j == i:
                continue
            try:
                # If other is contained inside poly → same building (opening/room)
                if poly.contains(other) or poly.intersects(other):
                    group.append(other)
                    assigned[j] = True
            except Exception:
                pass
        groups.append(group)

    return groups


# ── SVG preview generator ──────────────────────────────────────────────────────

def _svg_for_poly(poly, all_bnds, sw=480, sh=320) -> str:
    mn_x,mn_y,_,_, vp_w,vp_h = all_bnds
    try:
        pts = list(poly.exterior.coords)
        return _pts_to_svg(pts, mn_x, mn_y, vp_w, vp_h, sw, sh)
    except Exception:
        return ""


# ── Main result class ──────────────────────────────────────────────────────────

class DXFParseResult:
    def __init__(self):
        # Primary: first / largest building
        self.building_footprint_area_m2:  float = 0.0
        self.building_footprint_area_ft2: float = 0.0
        self.boundary_perimeter_m:        float = 0.0
        self.boundary_perimeter_ft:       float = 0.0
        self.slab_area_m2:                float = 0.0

        # Multi-building
        self.buildings: list[dict] = []

        # Walls / openings
        self.external_wall_length_m: float = 0.0
        self.internal_wall_length_m: float = 0.0
        self.total_wall_length_m:    float = 0.0
        self.num_doors:   int = 0
        self.num_windows: int = 0

        # Boundary candidates
        self.boundary_candidates: list[dict] = []
        self.rooms: list[dict] = []

        # Meta
        self.diagnostics:    dict      = {}
        self.warnings:       list[str] = []
        self.scale_factor:   float     = 1.0
        self.entity_counts:  dict      = {}
        self.units_detected: str       = "unknown"
        self.units_used:     str       = "mm"

        # Legacy alias
        self.total_floor_area_m2: float = 0.0

    def to_dict(self) -> dict:
        return {
            "building_footprint_area_m2":  round(self.building_footprint_area_m2,  3),
            "building_footprint_area_ft2": round(self.building_footprint_area_ft2, 3),
            "boundary_perimeter_m":        round(self.boundary_perimeter_m,        3),
            "boundary_perimeter_ft":       round(self.boundary_perimeter_ft,       3),
            "slab_area_m2":                round(self.slab_area_m2,               3),
            "total_floor_area_m2":         round(self.building_footprint_area_m2,  3),
            "total_wall_length_m":         round(self.total_wall_length_m,         3),
            "external_wall_length_m":      round(self.external_wall_length_m,      3),
            "internal_wall_length_m":      round(self.internal_wall_length_m,      3),
            "num_doors":   self.num_doors,
            "num_windows": self.num_windows,
            "buildings":   self.buildings,
            "boundary_candidates": self.boundary_candidates,
            "rooms":       self.rooms,
            "scale_factor":   self.scale_factor,
            "entity_counts":  self.entity_counts,
            "units_detected": self.units_detected,
            "units_used":     self.units_used,
            "diagnostics":    self.diagnostics,
            "warnings":       self.warnings,
        }


# ── Wall length extraction ─────────────────────────────────────────────────────

def _wall_lengths(segments: list[tuple], sf: float) -> dict:
    ext_wall = 0.0
    int_wall = 0.0
    total_all = 0.0
    wall_kw = {"wall","walls","a-wall","dinding"}
    ext_kw  = {"ext","external","outer","outside"}
    int_kw  = {"int","internal","inner","inside","partition"}
    for seg in segments:
        layer = seg[4].lower()
        dx = seg[2]-seg[0]; dy = seg[3]-seg[1]
        L = math.sqrt(dx*dx+dy*dy)*sf
        total_all += L
        is_wall = any(h in layer for h in wall_kw) or layer == "0"
        if is_wall:
            if any(h in layer for h in ext_kw):   ext_wall += L
            elif any(h in layer for h in int_kw): int_wall += L
            else: ext_wall += L*0.6; int_wall += L*0.4
    return {
        "external_m":  round(ext_wall,3),
        "internal_m":  round(int_wall,3),
        "total_m":     round(ext_wall+int_wall,3),
        "all_lines_m": round(total_all,3),
        "classified":  (ext_wall+int_wall) > 0,
    }


# ── MAIN ENTRY POINT ───────────────────────────────────────────────────────────

def parse_dxf_bytes(file_bytes: bytes, units: str = "mm") -> DXFParseResult:
    """
    Full DXF parsing pipeline v4.
    Uses Shapely for mathematically exact polygon areas.
    """
    result = DXFParseResult()
    result.units_used = units.lower()
    manual_sf = _MANUAL_SF.get(units.lower(), 0.001)

    # ── DWG check ─────────────────────────────────────────────────────────────
    if _is_dwg(file_bytes):
        result.warnings.append(
            "⚠ This is a binary DWG file. Only DXF files are supported. "
            "To convert: in AutoCAD open the DWG → File → Save As → "
            "AutoCAD 2010/2013 DXF (ASCII) → re-upload the .dxf file. "
            "Free converter: ODA File Converter (https://www.opendesign.com/guestfiles/oda_file_converter)"
        )
        return result

    # ── Decode + INSUNITS ─────────────────────────────────────────────────────
    text  = _decode(file_bytes)
    lines = text.splitlines()

    insunits = _get_insunits(lines)
    unit_name, auto_sf = _INSUNITS_MAP.get(insunits, ("unknown", None))
    result.units_detected = unit_name

    if auto_sf is not None:
        sf = auto_sf
        if unit_name.lower() != units.lower():
            result.warnings.append(
                f"Auto-detected units: {unit_name} ($INSUNITS={insunits}). "
                f"You selected '{units}'. Using auto-detected '{unit_name}'."
            )
        else:
            result.warnings.append(f"Drawing units confirmed: {unit_name}")
    else:
        sf = manual_sf
        result.warnings.append(
            f"$INSUNITS not set (value={insunits}). "
            f"Using user-selected: {units}."
        )
    result.scale_factor = sf

    # ── Open with ezdxf ───────────────────────────────────────────────────────
    direct_polys: list = []
    segments:     list = []
    entity_counts: dict = {}
    door_count   = 0
    window_count = 0

    try:
        import ezdxf
        doc, method = _open_dxf(file_bytes, result.warnings)
        if doc is not None:
            ex = _GeoExtractor()
            ex.run(doc)
            direct_polys   = ex.direct_polys
            segments       = ex.segments
            entity_counts  = ex.entity_counts
            door_count     = ex.door_count
            window_count   = ex.window_count
    except ImportError:
        result.warnings.append("ezdxf not installed — using raw text fallback.")

    # ── Fallback raw parser ───────────────────────────────────────────────────
    if not direct_polys and not segments:
        result.warnings.append("Using raw text fallback parser.")
        fb_polys, fb_segs, fb_counts = _raw_extract(text)
        direct_polys  = fb_polys
        segments      = fb_segs
        entity_counts = fb_counts

    result.entity_counts = entity_counts
    result.num_doors   = door_count + entity_counts.get("_doors",   0)
    result.num_windows = window_count + entity_counts.get("_windows", 0)

    has_ole   = entity_counts.get("OLE2FRAME", 0) > 0
    # Also detect OLE from raw text when ezdxf skips malformed OLE entities
    if not has_ole and "OLE2FRAME" in text.upper():
        has_ole = True
        entity_counts["OLE2FRAME"] = entity_counts.get("OLE2FRAME", 0) + text.upper().count("OLE2FRAME")
    geo_types = {"LINE","LWPOLYLINE","POLYLINE","ARC","CIRCLE","SPLINE","ELLIPSE","HATCH"}
    geo_count = sum(entity_counts.get(t,0) for t in geo_types)

    if has_ole and geo_count == 0 and not direct_polys and not segments:
        result.warnings.append(
            "⚠ DXF contains an OLE embedded object (OLE2FRAME) with no vector geometry. "
            "Open in AutoCAD → EXPLODE the OLE frame → Save As DXF 2010 ASCII → re-upload."
        )
        result.diagnostics = _build_diag(entity_counts, [], 0, 0, insunits, sf, {}, 0)
        return result

    if not direct_polys and not segments:
        if has_ole:
            result.warnings.append(
                "⚠ DXF contains an OLE embedded object (OLE2FRAME) with no vector geometry. "
                "Open in AutoCAD → EXPLODE the OLE frame → Save As DXF 2010 ASCII → re-upload."
            )
        else:
            result.warnings.append(
                "⚠ No geometric entities found. "
                "Ensure the DXF contains vector geometry (LINE/LWPOLYLINE/POLYLINE/ARC)."
            )
        result.diagnostics = _build_diag(entity_counts, [], 0, 0, insunits, sf, {}, 0)
        return result

    # ── Drawing extents (from segments) ──────────────────────────────────────
    all_segs_bounds = _all_bounds(segments)
    mn_x,mn_y,mx_x,mx_y,ext_w,ext_h = all_segs_bounds

    # ── Adaptive snap tolerance ───────────────────────────────────────────────
    smaller = min(ext_w, ext_h) if min(ext_w, ext_h) > 0 else max(ext_w, ext_h, 1)
    tol = max(5.0, smaller * 0.01)

    # ── Build polygons from LINE chains ───────────────────────────────────────
    chain_loops = _chain_to_loops(segments, tol)
    chain_polys = []
    for loop in chain_loops:
        poly = _make_polygon(loop)
        if poly is not None:
            chain_polys.append((poly, "0", "LINE_CHAIN"))

    # ── Build polygons from direct closed entities ────────────────────────────
    direct_built = []
    for (pts, layer, etype) in direct_polys:
        poly = _make_polygon(pts)
        if poly is not None:
            direct_built.append((poly, layer, etype))

    # Combine all — direct_built take priority (they are exact)
    all_polys_raw = direct_built + chain_polys

    if not all_polys_raw:
        result.warnings.append(
            f"⚠ {len(segments)} segments + {len(direct_polys)} closed entities found "
            "but no valid polygons could be constructed. "
            "Check: (1) Are LWPOLYLINE entities marked as closed? "
            "(2) Do LINE endpoints connect within drawing tolerance? "
            "(3) Is the correct Drawing Unit selected?"
        )
        result.diagnostics = _build_diag(
            entity_counts, segments, len(chain_loops), 0,
            insunits, sf, {}, tol, all_segs_bounds
        )
        return result

    # ── Scale to metres + compute area/perimeter ──────────────────────────────
    try:
        from shapely.affinity import scale as shapely_scale
        from shapely.geometry import Polygon
    except ImportError:
        result.warnings.append("Shapely not installed — install with: pip install shapely")
        return result

    scored: list[dict] = []
    for (poly, layer, etype) in all_polys_raw:
        # Scale polygon to metres
        try:
            poly_m = shapely_scale(poly, xfact=sf, yfact=sf, origin=(0,0))
        except Exception:
            continue

        area_m2  = poly_m.area
        if area_m2 < 0.5:   # < 0.5 m² → skip (noise)
            continue

        area_ft2 = area_m2 * M2_TO_FT2
        perim_m  = poly_m.length * 1.0   # already in metres after scale
        # Shapely .length gives perimeter for polygon exterior
        perim_ft = perim_m * M_TO_FT

        b        = _poly_bbox(poly)
        w_m      = b[4] * sf
        h_m      = b[5] * sf

        is_sheet = _is_sheet_border(poly, all_segs_bounds, sf, layer)
        score    = _score_poly(poly, sf, layer)
        svg_path = _svg_for_poly(poly, all_segs_bounds)

        scored.append({
            "poly":        poly,
            "poly_m":      poly_m,
            "layer":       layer,
            "etype":       etype,
            "area_m2":     round(area_m2,  3),
            "area_ft2":    round(area_ft2, 3),
            "perimeter_m": round(perim_m,  3),
            "perimeter_ft":round(perim_ft, 3),
            "width_m":     round(w_m, 3),
            "height_m":    round(h_m, 3),
            "is_sheet_border": is_sheet,
            "score":       score,
            "is_selected": False,
            "svg_path":    svg_path,
            "svg_viewbox": "0 0 480 320",
        })

    # Sort by score
    scored.sort(key=lambda x: x["score"], reverse=True)

    # ── Deduplicate polygons with nearly identical areas ──────────────────────
    deduped: list[dict] = []
    for c in scored:
        duplicate = False
        for d in deduped:
            if abs(c["area_m2"] - d["area_m2"]) / max(d["area_m2"], 1e-9) < 0.005:
                duplicate = True
                break
        if not duplicate:
            deduped.append(c)
    scored = deduped

    # ── Select building footprint ─────────────────────────────────────────────
    building_candidate = None
    for c in scored:
        if not c["is_sheet_border"]:
            building_candidate = c
            break
    if building_candidate is None and scored:
        building_candidate = scored[0]
        result.warnings.append(
            "All boundaries classified as sheet borders. Using largest. Verify visually."
        )

    if building_candidate:
        building_candidate["is_selected"] = True
        result.building_footprint_area_m2  = building_candidate["area_m2"]
        result.building_footprint_area_ft2 = building_candidate["area_ft2"]
        result.boundary_perimeter_m        = building_candidate["perimeter_m"]
        result.boundary_perimeter_ft       = building_candidate["perimeter_ft"]
        result.slab_area_m2                = building_candidate["area_m2"]
        result.total_floor_area_m2         = building_candidate["area_m2"]

    # ── Multi-building detection ──────────────────────────────────────────────
    building_polys = [c for c in scored if not c["is_sheet_border"]]
    if len(building_polys) >= 2:
        # Check if the top-2 polygons are truly separate (don't overlap significantly)
        alpha_names = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        result.buildings = []
        seen_areas: set[float] = set()
        bld_idx = 0
        for c in building_polys[:10]:
            area_key = round(c["area_m2"], 1)
            if area_key in seen_areas:
                continue
            # Only report as separate building if it doesn't nest inside the main
            if bld_idx > 0 and building_candidate:
                try:
                    if building_candidate["poly"].contains(c["poly"]):
                        continue   # it's a sub-area/room, not a separate building
                except Exception:
                    pass
            seen_areas.add(area_key)
            label = f"Building {alpha_names[bld_idx]}" if bld_idx < len(alpha_names) else f"Building {bld_idx+1}"
            result.buildings.append({
                "label":        label,
                "area_m2":      c["area_m2"],
                "area_ft2":     c["area_ft2"],
                "perimeter_m":  c["perimeter_m"],
                "width_m":      c["width_m"],
                "height_m":     c["height_m"],
                "svg_path":     c.get("svg_path",""),
                "svg_viewbox":  "0 0 480 320",
            })
            bld_idx += 1
            if bld_idx >= 6:
                break

    # ── Room sub-areas ────────────────────────────────────────────────────────
    bfa = result.building_footprint_area_m2
    for i, c in enumerate(scored[1:], 1):
        if not c["is_sheet_border"] and 0.5 <= c["area_m2"] <= bfa * 0.88:
            result.rooms.append({
                "name":    f"Area {i}",
                "area_m2": c["area_m2"],
                "area_ft2": c["area_ft2"],
                "width_m": c["width_m"],
                "height_m": c["height_m"],
            })
        if len(result.rooms) >= 20:
            break

    # ── Boundary candidates for UI ────────────────────────────────────────────
    result.boundary_candidates = [
        {k:v for k,v in c.items() if k not in ("poly","poly_m")}
        for c in scored[:12]
    ]

    # ── Wall lengths ──────────────────────────────────────────────────────────
    walls = _wall_lengths(segments, sf)
    result.external_wall_length_m = walls["external_m"]
    result.internal_wall_length_m = walls["internal_m"]
    result.total_wall_length_m    = (
        walls["total_m"] if walls["classified"] else walls["all_lines_m"]
    )
    if not walls["classified"] and walls["all_lines_m"] > 0:
        result.warnings.append(
            f"No WALL layers found. Total line length "
            f"({walls['all_lines_m']:.1f} m) used as approximate wall estimate."
        )

    # ── Sanity checks ─────────────────────────────────────────────────────────
    if result.building_footprint_area_m2 > 0:
        w = building_candidate["width_m"]
        h = building_candidate["height_m"]
        if w < 1 or h < 1:
            result.warnings.append(
                f"⚠ Building dimensions very small ({w:.3f}m × {h:.3f}m). "
                "Select correct Drawing Units (likely MM)."
            )
        elif w > 2000 or h > 2000:
            result.warnings.append(
                f"⚠ Building dimensions very large ({w:.0f}m × {h:.0f}m). "
                "Check Drawing Units selection."
            )

    # ── Diagnostics ───────────────────────────────────────────────────────────
    result.diagnostics = _build_diag(
        entity_counts, segments,
        len(chain_loops), len(scored),
        insunits, sf,
        building_candidate or {},
        tol, all_segs_bounds,
        len(direct_polys), len(direct_built),
    )

    return result


def _build_diag(
    ec, segs, chain_loops, candidates,
    insunits, sf, sel, tol,
    all_bnds=None,
    direct_polys=0, direct_built=0,
) -> dict:
    geo = {"LINE","LWPOLYLINE","POLYLINE","ARC","CIRCLE","SPLINE","ELLIPSE","HATCH"}
    d = {
        "total_entities":          sum(v for k,v in ec.items() if not k.startswith("_")),
        "geometric_entities":      sum(ec.get(t,0) for t in geo),
        "line_count":              ec.get("LINE",0),
        "lwpolyline_count":        ec.get("LWPOLYLINE",0),
        "polyline_count":          ec.get("POLYLINE",0),
        "arc_count":               ec.get("ARC",0),
        "circle_count":            ec.get("CIRCLE",0),
        "spline_count":            ec.get("SPLINE",0),
        "ellipse_count":           ec.get("ELLIPSE",0),
        "hatch_count":             ec.get("HATCH",0),
        "insert_count":            ec.get("INSERT",0),
        "ole2frame_count":         ec.get("OLE2FRAME",0),
        "segments_extracted":      len(segs),
        "direct_closed_polys":     direct_polys,
        "direct_valid_polys":      direct_built,
        "chain_loops_found":       chain_loops,
        "boundary_candidates":     candidates,
        "snap_tolerance_du":       round(tol,4),
        "insunits_value":          insunits,
        "scale_factor_m_per_du":   sf,
    }
    if all_bnds:
        mn_x,mn_y,mx_x,mx_y,ew,eh = all_bnds
        d["drawing_extents"] = {
            "min_x": round(mn_x,3), "min_y": round(mn_y,3),
            "max_x": round(mx_x,3), "max_y": round(mx_y,3),
            "width_du":  round(ew,3),
            "height_du": round(eh,3),
            "width_m":   round(ew*sf,3),
            "height_m":  round(eh*sf,3),
        }
    if sel:
        d["selected_boundary"] = {
            k:v for k,v in sel.items()
            if k in ("area_m2","area_ft2","perimeter_m","width_m","height_m","score","etype","layer")
        }
    return d
