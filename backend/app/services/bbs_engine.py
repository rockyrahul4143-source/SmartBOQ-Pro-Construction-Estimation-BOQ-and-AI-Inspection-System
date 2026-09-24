"""
BBS Calculation Engine — Professional Civil Engineering
=======================================================
Standards: IS 2502, IS 456-2000, SP-34, IS 13920

SINGLE SHARED ENGINE for both Manual BBS and Automatic BBS.
Manual input → this engine = Automatic extraction → this engine.

All inputs: mm.  All weights: kg.  All lengths: mm unless stated.
Every result carries: formula, inputs, calculation, result, standard_ref.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# ── Unit weights (kg/m) — IS 1786 ─────────────────────
UNIT_WEIGHT: Dict[int, float] = {
    6:0.222, 8:0.395, 10:0.617, 12:0.888, 16:1.580,
    20:2.469, 25:3.853, 28:4.834, 32:6.313, 36:7.990, 40:9.865,
}

NOT_FOUND = "NOT_FOUND / VERIFICATION REQUIRED"
CONFLICT  = "CONFLICT_DETECTED — VERIFY DRAWING"
VERIFY    = "VERIFY_REQUIRED"

def unit_weight_kg_per_m(dia: int) -> float:
    return UNIT_WEIGHT.get(dia, round(dia**2 / 162.0, 3))

# ── Hook lengths (IS 2502) ────────────────────────────
def hook_length(dia: int, hook_type: str = "standard") -> float:
    """
    IS 2502:
      180° (standard): max(9d, 75mm)
      90°:  8d
      135° (seismic):  same bend + 10d extension → used as 10d for 135
    """
    if hook_type in ("180", "standard"):
        return max(9*dia, 75.0)
    if hook_type == "90":
        return 8*dia
    if hook_type == "135":
        return 10*dia   # extension beyond bend per IS 13920
    return max(9*dia, 75.0)

# ── Bend deduction (IS 2502 Table 1) ─────────────────
def bend_deduction(dia: int, angle: float) -> float:
    if angle <= 45:   return 1.0*dia
    if angle <= 90:   return 2.0*dia
    return 3.0*dia

# ── Development length (IS 456 Cl.26.2) ─────────────
def development_length(dia: int, fck: int = 20, fy: int = 500,
                        bond_type: str = "deformed") -> float:
    tbd_table = {15:1.0, 20:1.2, 25:1.4, 30:1.5, 35:1.7, 40:1.9}
    tbd = tbd_table.get(fck, 1.2 + (fck-20)*0.04)
    if bond_type == "deformed": tbd *= 1.6
    ld = (0.87 * fy * dia) / (4 * tbd)
    return round(ld, 0)

# ── Lap length (IS 456 Cl.26.2.5) ───────────────────
def lap_length(dia: int, fck: int = 20, fy: int = 500,
               bond_type: str = "deformed", zone: str = "tension") -> float:
    ld  = development_length(dia, fck, fy, bond_type)
    fac = 1.3 if zone == "tension" else 1.0
    return max(round(ld*fac, 0), max(300.0, 24.0*dia))


# ═══════════════════════════════════════════════════════
# STIRRUP / TIE CALCULATIONS
# ═══════════════════════════════════════════════════════

@dataclass
class StirrupZone:
    """One spacing zone for stirrups/ties."""
    label:      str    = "Zone"
    length_mm:  float  = 0.0   # zone length (0 = derive from clear span)
    spacing_mm: float  = 150.0

@dataclass
class StirrupInput:
    b_mm:        float  # section breadth
    d_mm:        float  # section overall depth
    dia_mm:      int    = 8
    cover_mm:    float  = 25.0
    shape:       str    = "rect"    # rect|square|diamond|custom
    hook_type:   str    = "135"
    num_legs:    int    = 2
    # Zones — if empty, uses full clear_span with single spacing
    zones:       List[StirrupZone] = field(default_factory=list)
    clear_span_mm: float = 0.0      # fallback when no zones defined
    source:      str    = "manual"

@dataclass
class StirrupZoneResult:
    label:           str
    zone_length_mm:  float
    spacing_mm:      float
    num_stirrups:    int
    cutting_length_mm: float
    total_length_mm: float
    total_weight_kg: float

@dataclass
class StirrupResult:
    dia_mm:          int
    cutting_length_mm: float
    formula:         str
    calc_detail:     str
    standard_ref:    str
    zones:           List[StirrupZoneResult]
    total_num:       int
    total_length_mm: float
    unit_weight:     float
    total_weight_kg: float
    source:          str
    status:          str = "calculated"

def calc_stirrups(inp: StirrupInput, bar_id: str = "ST") -> StirrupResult:
    cover = inp.cover_mm
    ib    = inp.b_mm - 2*cover
    id_   = inp.d_mm - 2*cover

    if inp.shape == "diamond":
        side      = math.sqrt((ib/2)**2 + (id_/2)**2)
        perimeter = 4*side
    else:
        perimeter = 2*(ib + id_)

    # Hook allowance
    if inp.hook_type == "135":
        hook_add = 2 * 10 * inp.dia_mm          # two 135° hooks
    elif inp.hook_type == "90":
        hook_add = 2 * hook_length(inp.dia_mm, "90")
    else:
        hook_add = 2 * hook_length(inp.dia_mm)

    # Bend deduction: 4 bends × 90°
    bend_ded = 4 * bend_deduction(inp.dia_mm, 90)

    cl = perimeter + hook_add - bend_ded
    uw = unit_weight_kg_per_m(inp.dia_mm)

    formula = (
        f"Stirrup CL = 2×(b_inner + d_inner) + hooks - bends\n"
        f"  b_inner = {inp.b_mm} - 2×{cover} = {ib:.0f} mm\n"
        f"  d_inner = {inp.d_mm} - 2×{cover} = {id_:.0f} mm\n"
        f"  perimeter = 2×({ib:.0f}+{id_:.0f}) = {perimeter:.0f} mm\n"
        f"  hooks = 2×{10*inp.dia_mm} = {hook_add:.0f} mm  (2×135° @10d, IS 13920)\n"
        f"  bends = 4×{bend_deduction(inp.dia_mm,90):.0f} = {bend_ded:.0f} mm\n"
        f"  CL = {perimeter:.0f} + {hook_add:.0f} - {bend_ded:.0f} = {cl:.0f} mm"
    )

    zones_res: List[StirrupZoneResult] = []
    if inp.zones:
        for z in inp.zones:
            if z.spacing_mm <= 0:
                continue
            nos = math.ceil(z.length_mm / z.spacing_mm) + 1
            tl  = round(cl * nos, 0)
            wt  = round(tl / 1000 * uw, 3)
            zones_res.append(StirrupZoneResult(
                label=z.label, zone_length_mm=z.length_mm,
                spacing_mm=z.spacing_mm, num_stirrups=nos,
                cutting_length_mm=round(cl,0),
                total_length_mm=tl, total_weight_kg=wt,
            ))
    else:
        # Single zone using clear span
        span = inp.clear_span_mm
        nos  = math.ceil(span / inp.zones[0].spacing_mm) + 1 if inp.zones else (
               math.ceil(span / 150) + 1 if span > 0 else 0)
        tl   = round(cl * nos, 0)
        wt   = round(tl / 1000 * uw, 3)
        zones_res.append(StirrupZoneResult(
            label="Full Span", zone_length_mm=span,
            spacing_mm=150, num_stirrups=nos,
            cutting_length_mm=round(cl,0), total_length_mm=tl, total_weight_kg=wt,
        ))

    total_nos = sum(z.num_stirrups for z in zones_res)
    total_len = round(sum(z.total_length_mm for z in zones_res), 0)
    total_wt  = round(total_len / 1000 * uw, 3)

    return StirrupResult(
        dia_mm=inp.dia_mm, cutting_length_mm=round(cl,0),
        formula=formula,
        calc_detail=f"CL={cl:.0f}mm | {total_nos} stirrups | {total_len:.0f}mm total",
        standard_ref="IS 2502 / IS 13920",
        zones=zones_res, total_num=total_nos,
        total_length_mm=total_len, unit_weight=uw,
        total_weight_kg=total_wt, source=inp.source,
    )


# ═══════════════════════════════════════════════════════
# BEAM BAR CALCULATIONS
# ═══════════════════════════════════════════════════════

@dataclass
class BeamBarInput:
    clear_span_mm:        float
    support_near_mm:      float = 230.0
    support_far_mm:       float = 230.0
    dia_mm:               int   = 16
    num_bars:             int   = 2
    position:             str   = "bottom"    # bottom|top|extra_top|extra_bot|side_face
    has_hook_near:        bool  = True
    has_hook_far:         bool  = True
    hook_type:            str   = "standard"
    curtailment_near_mm:  float = 0.0   # length cut at near support
    curtailment_far_mm:   float = 0.0   # length cut at far support
    extra_length_near:    float = 0.0   # extension beyond support face
    extra_length_far:     float = 0.0
    splice_required:      bool  = False
    fck: int = 20;  fy: int = 500;  bond_type: str = "deformed"
    source: str = "manual"

@dataclass
class BeamBarResult:
    bar_id:          str
    dia_mm:          int
    num_bars:        int
    position:        str
    cutting_length_mm: float
    lap_length_mm:   float
    total_length_mm: float
    unit_weight:     float
    total_weight_kg: float
    formula:         str
    calc_detail:     str
    standard_ref:    str
    source:          str
    status:          str = "calculated"

def calc_beam_bar(inp: BeamBarInput, bar_id: str = "B1") -> BeamBarResult:
    anc_n = inp.support_near_mm / 2 + inp.extra_length_near
    anc_f = inp.support_far_mm  / 2 + inp.extra_length_far
    h_n   = hook_length(inp.dia_mm, inp.hook_type) if inp.has_hook_near else 0.0
    h_f   = hook_length(inp.dia_mm, inp.hook_type) if inp.has_hook_far  else 0.0

    # Curtailment shortens the bar
    curtail = inp.curtailment_near_mm + inp.curtailment_far_mm

    cl  = inp.clear_span_mm + anc_n + anc_f + h_n + h_f - curtail
    lap = lap_length(inp.dia_mm, inp.fck, inp.fy, inp.bond_type) if inp.splice_required else 0.0
    total_per = cl + lap
    total_all = total_per * inp.num_bars
    uw        = unit_weight_kg_per_m(inp.dia_mm)
    wt        = round(total_all / 1000 * uw, 3)

    formula = (
        f"CL = clear_span + anc_near + anc_far + hook_near + hook_far - curtailment\n"
        f"   = {inp.clear_span_mm:.0f} + {anc_n:.0f} + {anc_f:.0f}"
        f" + {h_n:.0f} + {h_f:.0f} - {curtail:.0f}\n"
        f"   = {cl:.0f} mm"
        + (f"\n  + lap ({lap:.0f} mm)" if lap else "")
    )
    return BeamBarResult(
        bar_id=bar_id, dia_mm=inp.dia_mm, num_bars=inp.num_bars,
        position=inp.position, cutting_length_mm=round(cl,0),
        lap_length_mm=round(lap,0), total_length_mm=round(total_all,0),
        unit_weight=uw, total_weight_kg=wt, formula=formula,
        calc_detail=f"CL={cl:.0f}mm × {inp.num_bars} bars = {total_all:.0f}mm",
        standard_ref="IS 2502 / IS 456 Cl.26.2", source=inp.source,
    )


# ═══════════════════════════════════════════════════════
# COLUMN BAR CALCULATIONS
# ═══════════════════════════════════════════════════════

@dataclass
class ColumnBarInput:
    storey_height_mm:  float
    dia_mm:            int   = 16
    num_bars:          int   = 4
    cover_mm:          float = 40.0
    lap_mm:            float = 0.0    # 0 = auto-calculate
    extra_top_mm:      float = 0.0    # projection above slab/beam
    is_starter:        bool  = False  # starter bars from footing
    lap_zone:          str   = "compression"
    fck:  int = 20;  fy: int = 500;  bond_type: str = "deformed"
    source: str = "manual"

@dataclass
class ColumnBarResult:
    bar_id:          str
    dia_mm:          int
    num_bars:        int
    cutting_length_mm: float
    lap_length_mm:   float
    total_length_mm: float
    unit_weight:     float
    total_weight_kg: float
    formula:         str
    calc_detail:     str
    standard_ref:    str
    source:          str
    status:          str = "calculated"

def calc_column_bar(inp: ColumnBarInput, bar_id: str = "C1-M") -> ColumnBarResult:
    auto_lap = lap_length(inp.dia_mm, inp.fck, inp.fy, inp.bond_type, inp.lap_zone)
    actual_lap = inp.lap_mm if inp.lap_mm > 0 else auto_lap
    cl  = inp.storey_height_mm + actual_lap + inp.extra_top_mm
    total = cl * inp.num_bars
    uw  = unit_weight_kg_per_m(inp.dia_mm)
    wt  = round(total / 1000 * uw, 3)
    formula = (
        f"CL = storey_height + lap + extra_top\n"
        f"   = {inp.storey_height_mm:.0f} + {actual_lap:.0f} + {inp.extra_top_mm:.0f}\n"
        f"   = {cl:.0f} mm\n"
        f"  (Lap = {'provided' if inp.lap_mm > 0 else 'auto IS456'}:"
        f" {actual_lap:.0f} mm)"
    )
    return ColumnBarResult(
        bar_id=bar_id, dia_mm=inp.dia_mm, num_bars=inp.num_bars,
        cutting_length_mm=round(cl,0), lap_length_mm=round(actual_lap,0),
        total_length_mm=round(total,0), unit_weight=uw, total_weight_kg=wt,
        formula=formula, calc_detail=f"CL={cl:.0f}mm × {inp.num_bars} bars",
        standard_ref="IS 456 Cl.26.2.5", source=inp.source,
    )


# ═══════════════════════════════════════════════════════
# SLAB BAR CALCULATIONS
# ═══════════════════════════════════════════════════════

@dataclass
class SlabBarInput:
    span_mm:         float
    support_mm:      float  = 230.0
    dia_mm:          int    = 10
    spacing_mm:      float  = 150.0
    slab_width_mm:   float  = 0.0    # perpendicular direction
    cover_mm:        float  = 15.0
    has_hooks:       bool   = False
    hook_type:       str    = "standard"
    is_extra_bar:    bool   = False  # top/extra bars
    curtailment_mm:  float  = 0.0
    fck: int = 20;  fy: int = 500
    source: str = "manual"

@dataclass
class SlabBarResult:
    dia_mm:          int
    direction:       str
    cutting_length_mm: float
    num_bars:        int
    total_length_mm: float
    unit_weight:     float
    total_weight_kg: float
    formula:         str
    standard_ref:    str
    source:          str
    status:          str = "calculated"

def calc_slab_bar(inp: SlabBarInput, direction: str = "main") -> SlabBarResult:
    anc = inp.support_mm / 2
    h   = hook_length(inp.dia_mm, inp.hook_type) if inp.has_hooks else 0.0
    cl  = inp.span_mm + 2*anc + 2*h - inp.curtailment_mm
    # Number of bars in perpendicular direction
    width = inp.slab_width_mm
    nos   = math.ceil(width / inp.spacing_mm) + 1 if width > 0 else 0
    uw    = unit_weight_kg_per_m(inp.dia_mm)
    total = round(cl * nos, 0)
    wt    = round(total / 1000 * uw, 3)
    formula = (
        f"CL = span + 2×anchorage + 2×hook - curtailment\n"
        f"   = {inp.span_mm:.0f} + 2×{anc:.0f} + 2×{h:.0f} - {inp.curtailment_mm:.0f}\n"
        f"   = {cl:.0f} mm\n"
        f"  No. bars = width({width:.0f}) / spacing({inp.spacing_mm:.0f}) + 1 = {nos}"
    )
    return SlabBarResult(
        dia_mm=inp.dia_mm, direction=direction,
        cutting_length_mm=round(cl,0), num_bars=nos,
        total_length_mm=total, unit_weight=uw, total_weight_kg=wt,
        formula=formula, standard_ref="IS 456 / IS 2502",
        source=inp.source,
    )


# ═══════════════════════════════════════════════════════
# FOOTING / FOUNDATION CALCULATIONS
# ═══════════════════════════════════════════════════════

@dataclass
class FootingBarInput:
    length_mm:   float
    width_mm:    float
    dia_mm:      int   = 12
    spacing_mm:  float = 150.0
    cover_mm:    float = 50.0
    has_hooks:   bool  = False
    direction:   str   = "length"   # length|width
    source:      str   = "manual"

def calc_footing_bar(inp: FootingBarInput, direction: str = "length") -> SlabBarResult:
    span = inp.length_mm if direction == "length" else inp.width_mm
    perp = inp.width_mm  if direction == "length" else inp.length_mm
    anc  = inp.cover_mm
    h    = hook_length(inp.dia_mm) if inp.has_hooks else 0.0
    cl   = span - 2*inp.cover_mm + 2*h
    nos  = math.ceil((perp - 2*inp.cover_mm) / inp.spacing_mm) + 1
    uw   = unit_weight_kg_per_m(inp.dia_mm)
    total = round(cl * nos, 0)
    wt    = round(total / 1000 * uw, 3)
    formula = (
        f"Footing bar CL = length - 2×cover + 2×hook\n"
        f"   = {span:.0f} - 2×{inp.cover_mm:.0f} + 2×{h:.0f} = {cl:.0f} mm\n"
        f"  Nos = (width - 2×cover) / spacing + 1 = {nos}"
    )
    return SlabBarResult(
        dia_mm=inp.dia_mm, direction=direction,
        cutting_length_mm=round(cl,0), num_bars=nos,
        total_length_mm=total, unit_weight=uw, total_weight_kg=wt,
        formula=formula, standard_ref="IS 456 / SP-34", source=inp.source,
    )


# ═══════════════════════════════════════════════════════
# DIAMETER SUMMARY
# ═══════════════════════════════════════════════════════

def diameter_summary(bar_rows: list[dict]) -> dict:
    summary: dict = {}
    for row in bar_rows:
        d = int(row.get("dia_mm") or 0)
        if d <= 0: continue
        s = summary.setdefault(d, {"dia_mm":d,"total_length_m":0.0,"total_weight_kg":0.0,"num_bars":0})
        s["total_length_m"]  += (row.get("total_length_mm") or 0) / 1000
        s["total_weight_kg"] += row.get("total_weight_kg") or 0
        s["num_bars"]        += int(row.get("num_bars") or 0)
    for d in summary:
        summary[d]["total_length_m"]  = round(summary[d]["total_length_m"],  3)
        summary[d]["total_weight_kg"] = round(summary[d]["total_weight_kg"], 3)
    return summary
