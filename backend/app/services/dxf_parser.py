"""
DXF Parser Service
==================
Handles real AutoCAD architectural DXF files.

Pipeline:
  1. Decode DXF bytes → ezdxf document (uses ezdxf.read with StringIO)
  2. Read $INSUNITS for unit detection
  3. Iterate modelspace + resolve INSERT/BLOCK references via virtual_entities()
  4. Extract LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, SPLINE segments
  5. Build closed loops from connected segment chains (adaptive snap tolerance)
  6. Filter sheet/title/annotation boundaries
  7. Select outer building footprint = largest valid closed loop
  8. Classify wall lengths, detect doors/windows from INSERT block names
  9. Return full result with diagnostics

Fixed vs previous version:
  - ezdxf.from_bytes() → ezdxf.read(io.StringIO(...))  [ezdxf 1.x API]
  - Correctly resolves INSERT/BLOCK geometry via virtual_entities()
  - Raw text fallback when ezdxf fails
"""
from __future__ import annotations
import io
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────
M2_TO_FT2 = 10.7639
M_TO_FT   = 3.28084

# Layer name hints
_TITLEBLOCK_HINTS = {
    "titleblock","title","titleblk","title_block","border","sheet",
    "defpoints","viewport","vport","frame","tb","logo","revision","rev",
}
_ARCH_HINTS = {
    "wall","walls","a-wall","arch","archwall","ext_wall","int_wall",
    "partition","slab","floor","structure","struct","column","col",
    "beam","room","outline","boundary","bldg","building","footprint",
    "plan","gf","ff","roof","terrace",
}
_DOOR_HINTS    = {"door","dr","pintu","d-","swng","swing"}
_WINDOW_HINTS  = {"window","win","casement","jendela","w-","wdw"}

# INSUNITS → (name, metres_per_unit)
_INSUNITS_MAP = {
    0:("unknown",  None),  1:("inches",  0.0254),  2:("feet",   0.3048),
    4:("mm",       0.001), 5:("cm",      0.01),    6:("m",      1.0),
    7:("km",       1000.0),
}
_MANUAL_SF = {"mm":0.001,"cm":0.01,"m":1.0,"ft":0.3048,"in":0.0254}


# ─────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────
def _dist(a, b) -> float:
    return math.hypot(a[0]-b[0], a[1]-b[1])

def _shoelace(pts) -> float:
    n = len(pts)
    if n < 3: return 0.0
    s = sum(pts[i][0]*pts[(i+1)%n][1] - pts[(i+1)%n][0]*pts[i][1] for i in range(n))
    return abs(s) / 2.0

def _arc_pts(cx, cy, r, a1_deg, a2_deg, n=16):
    a1, a2 = math.radians(a1_deg), math.radians(a2_deg)
    if a2 <= a1: a2 += 2*math.pi
    return [(cx+r*math.cos(a1+(a2-a1)*k/n), cy+r*math.sin(a1+(a2-a1)*k/n)) for k in range(n+1)]

def _circle_pts(cx, cy, r, n=32):
    return [(cx+r*math.cos(2*math.pi*k/n), cy+r*math.sin(2*math.pi*k/n)) for k in range(n)]


# ─────────────────────────────────────────────────────
# Segment
# ─────────────────────────────────────────────────────
class Segment:
    __slots__ = ("x1","y1","x2","y2","layer","etype")
    def __init__(self, x1,y1,x2,y2, layer="0", etype="LINE"):
        self.x1=float(x1); self.y1=float(y1)
        self.x2=float(x2); self.y2=float(y2)
        self.layer=str(layer).upper(); self.etype=etype
    def length(self): return _dist((self.x1,self.y1),(self.x2,self.y2))


# ─────────────────────────────────────────────────────
# ezdxf extraction  (CORRECT API for ezdxf 1.x)
# ─────────────────────────────────────────────────────
def _load_doc(raw: bytes):
    """Load ezdxf document from bytes. Works with ezdxf 0.x and 1.x."""
    import ezdxf
    # Strip binary/OLE embedded sections that break ezdxf text parsing
    # Binary embedded data appears after "ACDSDATA" or binary marker sections
    for enc in ("utf-8", "cp1252", "latin-1", "cp850"):
        try:
            text = raw.decode(enc, errors="replace")
            # Remove binary embedded sections that cause "Invalid binary data" errors
            # These appear as non-printable characters in the text
            clean_lines = []
            skip = False
            for line in text.splitlines():
                stripped = line.strip()
                # Skip ACDSDATA section (AutoCAD Design Center data - pure binary)
                if stripped == "ACDSDATA":
                    skip = True
                if not skip:
                    clean_lines.append(line)
                if skip and stripped == "ENDSEC":
                    skip = False
            clean_text = "\n".join(clean_lines)
            stream = io.StringIO(clean_text)
            doc = ezdxf.read(stream)
            return doc
        except Exception:
            pass
    raise ValueError("Could not parse DXF with ezdxf")


def _collect_segments_ezdxf(raw: bytes):
    """Use ezdxf to extract all geometry segments including BLOCK references."""
    segments = []
    entity_counts = {}
    warnings = []
    door_count = window_count = insert_count = 0

    try:
        import ezdxf
    except ImportError:
        warnings.append("ezdxf not installed — falling back to raw text parser")
        return segments, entity_counts, warnings

    try:
        doc = _load_doc(raw)
    except Exception as e:
        warnings.append(f"ezdxf failed to open file: {e} — falling back to raw parser")
        return segments, entity_counts, warnings

    msp = doc.modelspace()

    # Read $INSUNITS from header
    try:
        insunits_val = doc.header.get("$INSUNITS", 0)
        entity_counts["_insunits"] = insunits_val
    except Exception:
        entity_counts["_insunits"] = 0

    def _process(e):
        nonlocal door_count, window_count, insert_count
        etype = e.dxftype()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

        try:
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "0"
        except Exception:
            layer = "0"

        if etype == "OLE2FRAME":
            return

        # ── LINE ──────────────────────────────────────
        if etype == "LINE":
            try:
                p1, p2 = e.dxf.start, e.dxf.end
                seg = Segment(p1.x,p1.y, p2.x,p2.y, layer, "LINE")
                if seg.length() > 1e-9: segments.append(seg)
            except Exception: pass

        # ── LWPOLYLINE ────────────────────────────────
        elif etype == "LWPOLYLINE":
            try:
                pts = [(p[0],p[1]) for p in e.get_points()]
                if len(pts) < 2: return
                closed = e.closed
                if closed: pts = list(pts)+[pts[0]]
                for k in range(len(pts)-1):
                    seg = Segment(pts[k][0],pts[k][1],pts[k+1][0],pts[k+1][1],layer,"LWPOLYLINE")
                    if seg.length()>1e-9: segments.append(seg)
            except Exception: pass

        # ── POLYLINE ──────────────────────────────────
        elif etype == "POLYLINE":
            try:
                pts = [(v.dxf.location.x,v.dxf.location.y) for v in e.vertices]
                if len(pts) < 2: return
                closed = bool(e.dxf.get("flags",0) & 1)
                if closed: pts = pts+[pts[0]]
                for k in range(len(pts)-1):
                    seg = Segment(pts[k][0],pts[k][1],pts[k+1][0],pts[k+1][1],layer,"POLYLINE")
                    if seg.length()>1e-9: segments.append(seg)
            except Exception: pass

        # ── ARC ───────────────────────────────────────
        elif etype == "ARC":
            try:
                cx,cy,r = e.dxf.center.x,e.dxf.center.y,e.dxf.radius
                ap = _arc_pts(cx,cy,r,e.dxf.start_angle,e.dxf.end_angle,16)
                for k in range(len(ap)-1):
                    seg = Segment(ap[k][0],ap[k][1],ap[k+1][0],ap[k+1][1],layer,"ARC")
                    if seg.length()>1e-9: segments.append(seg)
            except Exception: pass

        # ── CIRCLE ────────────────────────────────────
        elif etype == "CIRCLE":
            try:
                cx,cy,r = e.dxf.center.x,e.dxf.center.y,e.dxf.radius
                cp = _circle_pts(cx,cy,r,32)+[_circle_pts(cx,cy,r,32)[0]]
                for k in range(len(cp)-1):
                    seg = Segment(cp[k][0],cp[k][1],cp[k+1][0],cp[k+1][1],layer,"CIRCLE")
                    if seg.length()>1e-9: segments.append(seg)
            except Exception: pass

        # ── SPLINE ────────────────────────────────────
        elif etype == "SPLINE":
            try:
                pts_s = [(p.x,p.y) for p in e.approximate(segments=20)]
                for k in range(len(pts_s)-1):
                    seg = Segment(pts_s[k][0],pts_s[k][1],pts_s[k+1][0],pts_s[k+1][1],layer,"SPLINE")
                    if seg.length()>1e-9: segments.append(seg)
            except Exception: pass

        # ── INSERT (block reference) ──────────────────
        elif etype == "INSERT":
            insert_count += 1
            try:
                bname = (e.dxf.name if e.dxf.hasattr("name") else "").upper()
                combined = bname + " " + layer.lower()
                if any(h in combined.lower() for h in _DOOR_HINTS):
                    door_count += 1
                elif any(h in combined.lower() for h in _WINDOW_HINTS):
                    window_count += 1
                # Explode block geometry
                try:
                    for child in e.virtual_entities():
                        _process(child)
                except Exception:
                    pass
            except Exception: pass

    try:
        for ent in msp:
            _process(ent)
    except Exception as ex:
        warnings.append(f"Error iterating modelspace: {ex}")

    entity_counts["_doors"]   = door_count
    entity_counts["_windows"] = window_count
    entity_counts["_inserts"] = insert_count
    return segments, entity_counts, warnings


# ─────────────────────────────────────────────────────
# Raw text fallback (when ezdxf unavailable)
# ─────────────────────────────────────────────────────
def _collect_segments_raw(raw: bytes):
    segments = []
    entity_counts = {}
    warnings = ["Using raw text fallback parser."]
    door_count = window_count = 0

    for enc in ("utf-8","cp1252","latin-1"):
        try:
            text = raw.decode(enc); break
        except Exception:
            pass
    else:
        text = raw.decode("utf-8", errors="replace")

    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        if lines[i].strip() == "0" and i+1 < n:
            etype = lines[i+1].strip().upper()
            entity_counts[etype] = entity_counts.get(etype,0)+1
            pts10,pts20,layer_val,gc = [],[],  "0",{}
            j = i+2
            while j < n and lines[j].strip() != "0":
                c = lines[j].strip()
                if j+1 < n:
                    v = lines[j+1].strip()
                    if c == "8":    layer_val = v
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
            if etype == "LINE" and len(pts10)>=2 and len(pts20)>=2:
                seg = Segment(pts10[0],pts20[0],pts10[1],pts20[1],layer_val,"LINE")
                if seg.length()>1e-9: segments.append(seg)
            elif etype == "LWPOLYLINE" and len(pts10)>=2 and len(pts20)>=2:
                flags = int(gc.get("70",0))
                pts = list(zip(pts10,pts20))
                if bool(flags&1): pts = pts+[pts[0]]
                for k in range(len(pts)-1):
                    seg = Segment(pts[k][0],pts[k][1],pts[k+1][0],pts[k+1][1],layer_val,"LWPOLYLINE")
                    if seg.length()>1e-9: segments.append(seg)
            elif etype == "INSERT":
                bname = str(gc.get("2","")).upper()
                combined = bname+" "+layer_val.lower()
                if any(h in combined.lower() for h in _DOOR_HINTS): door_count+=1
                elif any(h in combined.lower() for h in _WINDOW_HINTS): window_count+=1
        i += 1
    entity_counts["_doors"]   = door_count
    entity_counts["_windows"] = window_count
    return segments, entity_counts, warnings


# ─────────────────────────────────────────────────────
# Loop builder
# ─────────────────────────────────────────────────────
def _snap(p, tol):
    if tol <= 0: return p
    return (round(p[0]/tol)*tol, round(p[1]/tol)*tol)


def _build_loops(segments, tol=10.0):
    if not segments: return []
    from collections import defaultdict
    adj = defaultdict(list)
    eps = [(  _snap((s.x1,s.y1),tol), _snap((s.x2,s.y2),tol)  ) for s in segments]
    for idx,(p1,p2) in enumerate(eps):
        adj[p1].append(idx)
        adj[p2].append(idx)

    used, loops = set(), []

    def _chain(start):
        if start in used: return None
        p1,p2 = eps[start]
        chain = [p1,p2]
        chain_set = {start}
        used.add(start)
        head, tail = p1, p2
        for _ in range(len(segments)):
            cands = [i for i in adj[tail] if i not in chain_set]
            if not cands: break
            nxt = cands[0]
            a,b = eps[nxt]
            next_pt = b if a==tail else a
            chain.append(next_pt)
            chain_set.add(nxt)
            used.add(nxt)
            tail = next_pt
            if tail == head and len(chain) >= 4:
                return chain[:-1]
        return None

    for idx in range(len(segments)):
        if idx in used: continue
        lp = _chain(idx)
        if lp and len(lp) >= 3: loops.append(lp)
    return loops


def _bounds_all(segments):
    if not segments: return 0,0,0,0,0,0
    xs = [s.x1 for s in segments]+[s.x2 for s in segments]
    ys = [s.y1 for s in segments]+[s.y2 for s in segments]
    mx,Mx,my,My = min(xs),max(xs),min(ys),max(ys)
    return mx,my,Mx,My,Mx-mx,My-my

def _loop_bounds(lp):
    xs,ys = [p[0] for p in lp],[p[1] for p in lp]
    mx,Mx,my,My = min(xs),max(xs),min(ys),max(ys)
    return mx,my,Mx,My,Mx-mx,My-my

def _is_sheet(lp, all_bounds, sf):
    mx,my,Mx,My,tw,th = all_bounds
    if tw<1e-6 or th<1e-6: return False
    _,_,_,_,lw,lh = _loop_bounds(lp)
    if lw/tw>0.85 and lh/th>0.85: return True
    lw_m,lh_m = lw*sf,lh*sf
    # Typical A-series sheet sizes in metres
    if (0.15<lw_m<2.5) and (0.1<lh_m<2.0):
        area_m2 = _shoelace(lp)*sf*sf
        if area_m2 < 10: return True   # tiny "building" → sheet element
    return False


# ─────────────────────────────────────────────────────
# Wall lengths
# ─────────────────────────────────────────────────────
def _wall_lengths(segments, sf):
    ext=int_=total=all_=0.0
    wall_h = {"wall","walls","a-wall","dinding","partition","ext_wall","int_wall"}
    ext_h  = {"ext","external","outer","outside","extwall","ext_wall","outer_wall"}
    int_h  = {"int","internal","inner","inside","intwall","int_wall"}
    for seg in segments:
        L = seg.length()*sf
        all_ += L
        layer = seg.layer.lower()
        is_wall = any(h in layer for h in wall_h) or layer == "0"
        if is_wall:
            if any(h in layer for h in ext_h):   ext  += L
            elif any(h in layer for h in int_h): int_ += L
            else:                                 ext+=L*0.5; int_+=L*0.5
    return {"external_m":round(ext,3),"internal_m":round(int_,3),
            "total_m":round(ext+int_,3),"all_lines_m":round(all_,3)}


# ─────────────────────────────────────────────────────
# INSUNITS from raw text (fallback)
# ─────────────────────────────────────────────────────
def _get_insunits_raw(raw: bytes) -> int:
    for enc in ("utf-8","cp1252","latin-1"):
        try:
            text = raw.decode(enc); break
        except Exception: pass
    else:
        return 0
    lines = text.splitlines()
    for i,l in enumerate(lines):
        if l.strip() == "$INSUNITS" and i+2 < len(lines):
            try: return int(lines[i+2].strip())
            except: pass
    return 0


# ─────────────────────────────────────────────────────
# Result class
# ─────────────────────────────────────────────────────
class DXFParseResult:
    def __init__(self):
        self.building_footprint_area_m2  = 0.0
        self.building_footprint_area_ft2 = 0.0
        self.boundary_perimeter_m        = 0.0
        self.boundary_perimeter_ft       = 0.0
        self.slab_area_m2                = 0.0
        self.total_floor_area_m2         = 0.0  # legacy
        self.external_wall_length_m      = 0.0
        self.internal_wall_length_m      = 0.0
        self.total_wall_length_m         = 0.0
        self.num_doors    = 0
        self.num_windows  = 0
        self.boundary_candidates: list = []
        self.rooms:  list = []
        self.diagnostics: dict = {}
        self.warnings: list = []
        self.scale_factor    = 1.0
        self.entity_counts:  dict = {}
        self.units_detected  = "unknown"
        self.units_used      = "mm"

    def to_dict(self):
        return {
            "building_footprint_area_m2":  round(self.building_footprint_area_m2,  3),
            "building_footprint_area_ft2": round(self.building_footprint_area_ft2, 3),
            "boundary_perimeter_m":        round(self.boundary_perimeter_m,        3),
            "boundary_perimeter_ft":       round(self.boundary_perimeter_ft,       3),
            "slab_area_m2":                round(self.slab_area_m2,                3),
            "total_floor_area_m2":         round(self.building_footprint_area_m2,  3),
            "total_wall_length_m":         round(self.total_wall_length_m,         3),
            "external_wall_length_m":      round(self.external_wall_length_m,      3),
            "internal_wall_length_m":      round(self.internal_wall_length_m,      3),
            "num_doors":   self.num_doors,
            "num_windows": self.num_windows,
            "boundary_candidates": self.boundary_candidates,
            "rooms":       self.rooms,
            "scale_factor":      self.scale_factor,
            "entity_counts":     self.entity_counts,
            "units_detected":    self.units_detected,
            "units_used":        self.units_used,
            "diagnostics":       self.diagnostics,
            "warnings":          self.warnings,
        }


# ─────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────
def parse_dxf_bytes(file_bytes: bytes, units: str = "mm") -> DXFParseResult:
    result = DXFParseResult()
    result.units_used = units
    manual_sf = _MANUAL_SF.get(units.lower(), 0.001)

    # ── Try ezdxf first ───────────────────────────────
    segments, entity_counts, ezdxf_warns = _collect_segments_ezdxf(file_bytes)
    result.warnings.extend(ezdxf_warns)

    # ── Fallback to raw if ezdxf got nothing ──────────
    if not segments:
        raw_segs, raw_counts, raw_warns = _collect_segments_raw(file_bytes)
        result.warnings.extend(raw_warns)
        for k,v in raw_counts.items():
            entity_counts[k] = entity_counts.get(k,0)+v
        segments = raw_segs

    result.entity_counts = entity_counts

    # ── INSUNITS ──────────────────────────────────────
    insunits = int(entity_counts.get("_insunits", 0)) or _get_insunits_raw(file_bytes)
    unit_name, auto_sf = _INSUNITS_MAP.get(insunits, ("unknown", None))
    result.units_detected = unit_name

    if auto_sf is not None:
        sf = auto_sf
        if unit_name.lower() != units.lower():
            result.warnings.append(
                f"Auto-detected unit: {unit_name} ($INSUNITS={insunits}). "
                f"You selected '{units}'. Using auto-detected value. "
                "If area seems wrong, change Drawing Units to match the DXF."
            )
    else:
        sf = manual_sf
        result.warnings.append(
            f"$INSUNITS not set (value={insunits}). Using selected units: {units}."
        )
    result.scale_factor = sf

    # ── Entity type counts for diagnostics ───────────
    geo_types = {"LINE","LWPOLYLINE","POLYLINE","ARC","CIRCLE","SPLINE"}
    geo_count = sum(entity_counts.get(t,0) for t in geo_types)
    total_ents = sum(v for k,v in entity_counts.items() if not k.startswith("_"))
    has_ole = entity_counts.get("OLE2FRAME",0) > 0

    result.diagnostics = {
        "total_entities":      total_ents,
        "geometric_entities":  geo_count,
        "line_count":          entity_counts.get("LINE",0),
        "lwpolyline_count":    entity_counts.get("LWPOLYLINE",0),
        "polyline_count":      entity_counts.get("POLYLINE",0),
        "arc_count":           entity_counts.get("ARC",0),
        "circle_count":        entity_counts.get("CIRCLE",0),
        "spline_count":        entity_counts.get("SPLINE",0),
        "insert_count":        entity_counts.get("_inserts",0),
        "ole2frame_count":     entity_counts.get("OLE2FRAME",0),
        "segments_extracted":  len(segments),
        "insunits_value":      insunits,
        "scale_factor":        sf,
    }

    # OLE-only warning
    if has_ole and geo_count == 0 and not segments:
        result.warnings.append(
            "⚠ DXF contains an embedded OLE object (OLE2FRAME) but NO vector geometry found. "
            "To fix: open in AutoCAD → EXPLODE the OLE frame → Save As DXF 2010 ASCII."
        )
        return result

    if not segments:
        result.warnings.append(
            "No geometric segments found. Ensure DXF contains standard LINE/POLYLINE geometry."
        )
        return result

    # ── Drawing extents ───────────────────────────────
    mn_x,mn_y,mx_x,mx_y,ext_w,ext_h = _bounds_all(segments)
    result.diagnostics["drawing_extents"] = {
        "min_x": round(mn_x,3), "min_y": round(mn_y,3),
        "max_x": round(mx_x,3), "max_y": round(mx_y,3),
        "width_drawing_units":  round(ext_w,3),
        "height_drawing_units": round(ext_h,3),
        "width_m":  round(ext_w*sf,3),
        "height_m": round(ext_h*sf,3),
    }

    # ── Adaptive snap tolerance ───────────────────────
    tol = max(0.1, min(ext_w,ext_h)*0.001)
    result.diagnostics["snap_tolerance"] = round(tol,6)

    # ── Build closed loops ────────────────────────────
    loops = _build_loops(segments, tol=tol)
    if not loops:
        loops = _build_loops(segments, tol=tol*20)
        if loops:
            result.warnings.append(
                f"No loops at tight tolerance. Used ×20 tolerance → {len(loops)} loop(s). "
                "Drawing may have small endpoint gaps."
            )
    result.diagnostics["closed_loops_found"] = len(loops)

    all_bounds = (mn_x,mn_y,mx_x,mx_y,ext_w,ext_h)

    # ── Score each loop ───────────────────────────────
    candidates = []
    for lp in loops:
        area_raw = _shoelace(lp)
        if area_raw < 1e-6: continue
        area_m2  = area_raw * sf * sf
        if area_m2 < 0.01: continue   # skip loops smaller than 0.01 m²
        area_ft2 = area_m2 * M2_TO_FT2
        _,_,_,_,lw,lh = _loop_bounds(lp)
        perim_raw = sum(_dist(lp[k],lp[(k+1)%len(lp)]) for k in range(len(lp)))
        perim_m   = perim_raw * sf

        is_sheet = _is_sheet(lp, all_bounds, sf)
        score    = area_raw * (0.01 if is_sheet else 1.0)

        candidates.append({
            "area_m2":        round(area_m2,3),
            "area_ft2":       round(area_ft2,3),
            "perimeter_m":    round(perim_m,3),
            "perimeter_ft":   round(perim_m*M_TO_FT,3),
            "width_m":        round(lw*sf,3),
            "height_m":       round(lh*sf,3),
            "is_sheet_border": is_sheet,
            "score":          score,
            "pts_count":      len(lp),
            "loop":           lp,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    result.boundary_candidates = [{k:v for k,v in c.items() if k!="loop"} for c in candidates[:10]]
    result.diagnostics["boundary_candidates_count"] = len(candidates)

    # ── Select building footprint ─────────────────────
    best = next((c for c in candidates if not c["is_sheet_border"]), None)
    if best is None and candidates:
        # Check: largest candidate vs extents
        # If largest candidate area is < 5% of extents area → it's just symbols, not the building
        extents_area_m2 = ext_w * ext_h * sf * sf
        largest_area    = candidates[0]["area_m2"] if candidates else 0
        if extents_area_m2 > 0 and largest_area < extents_area_m2 * 0.05:
            # All loops are symbols — skip to extents fallback
            best = None
        else:
            best = candidates[0]
            result.warnings.append("All boundaries look like sheet borders — using largest. Verify visually.")

    if best:
        result.building_footprint_area_m2  = best["area_m2"]
        result.building_footprint_area_ft2 = best["area_ft2"]
        result.boundary_perimeter_m        = best["perimeter_m"]
        result.boundary_perimeter_ft       = best["perimeter_ft"]
        result.slab_area_m2                = best["area_m2"]
        result.total_floor_area_m2         = best["area_m2"]
        result.diagnostics["selected_boundary"] = {
            "area_m2":    best["area_m2"],
            "width_m":    best["width_m"],
            "height_m":   best["height_m"],
            "perimeter_m": best["perimeter_m"],
        }
    else:
        # ── FALLBACK: use drawing extents if loops failed ────
        # This happens when lines don't form closed polylines
        # but drawing extents clearly show the building footprint
        if ext_w > 0 and ext_h > 0:
            ext_area_m2 = ext_w * ext_h * sf * sf
            # Only use extents if they look like a realistic building (1–5000 m²)
            if 1.0 <= ext_area_m2 <= 5000:
                result.building_footprint_area_m2  = round(ext_area_m2, 3)
                result.building_footprint_area_ft2 = round(ext_area_m2 * M2_TO_FT2, 3)
                perim_m = 2 * (ext_w + ext_h) * sf
                result.boundary_perimeter_m   = round(perim_m, 3)
                result.boundary_perimeter_ft  = round(perim_m * M_TO_FT, 3)
                result.slab_area_m2           = result.building_footprint_area_m2
                result.total_floor_area_m2    = result.building_footprint_area_m2
                result.diagnostics["selected_boundary"] = {
                    "area_m2":     result.building_footprint_area_m2,
                    "width_m":     round(ext_w*sf, 3),
                    "height_m":    round(ext_h*sf, 3),
                    "perimeter_m": result.boundary_perimeter_m,
                    "source":      "drawing_extents_fallback",
                }
                result.warnings.append(
                    f"No closed boundary polylines found. Used drawing extents as building footprint "
                    f"({round(ext_w*sf,2)}m × {round(ext_h*sf,2)}m = {result.building_footprint_area_m2} m²). "
                    "For more accurate results, draw the building outline as a closed polyline in AutoCAD."
                )
            else:
                result.warnings.append(
                    f"⚠ {len(segments)} segments found but no valid closed boundary detected. "
                    f"Drawing extents ({round(ext_w*sf,1)}m × {round(ext_h*sf,1)}m) outside expected range. "
                    "Try: 1) Close polylines in AutoCAD 2) Change Drawing Units selection."
                )
        else:
            result.warnings.append(
                f"⚠ {len(segments)} segments found but no closed boundary detected. "
                "Possible causes: 1) Polylines not closed in AutoCAD. "
                "2) Small gaps between line endpoints. "
                "3) Try a different Drawing Units selection."
            )

    # ── Rooms ─────────────────────────────────────────
    bfa = result.building_footprint_area_m2
    for i,c in enumerate(candidates[1:],1):
        if not c["is_sheet_border"] and 0.01 < c["area_m2"] < bfa*0.9:
            result.rooms.append({"name":f"Area {i}","area_m2":c["area_m2"],"area_ft2":c["area_ft2"]})
        if len(result.rooms) >= 20: break

    # ── Wall lengths ──────────────────────────────────
    walls = _wall_lengths(segments, sf)
    result.external_wall_length_m = walls["external_m"]
    result.internal_wall_length_m = walls["internal_m"]
    result.total_wall_length_m    = walls["total_m"] if walls["total_m"]>0 else walls["all_lines_m"]
    result.diagnostics["wall_extraction"] = walls

    # ── Doors / Windows ───────────────────────────────
    result.num_doors   = entity_counts.get("_doors",  0)
    result.num_windows = entity_counts.get("_windows",0)

    # ── Sanity checks ─────────────────────────────────
    if result.building_footprint_area_m2 > 0:
        w = result.diagnostics.get("selected_boundary",{}).get("width_m",0)
        h = result.diagnostics.get("selected_boundary",{}).get("height_m",0)
        if w>0 and h>0:
            if w<1 or h<1:
                result.warnings.append(
                    f"⚠ Building dimensions very small: {w:.3f}m × {h:.3f}m. "
                    "If drawing is in mm, select MM as drawing units."
                )
            elif w>500 or h>500:
                result.warnings.append(
                    f"⚠ Building dimensions very large: {w:.0f}m × {h:.0f}m. "
                    "If you selected MM but drawing is actually in m, try selecting M."
                )

    return result
