"""
BBS Calculation Engine
======================
Shared deterministic engine for BOTH manual and automatic BBS.
Manual entry → this engine → same result as automatic extraction → this engine.

Standards: IS 2502, SP-34, IS 456-2000
All inputs in mm. All outputs in mm and kg.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Bar unit weights (kg/m) — IS 1786 ─────────────────
UNIT_WEIGHT: dict[int, float] = {
    6:   0.222,
    8:   0.395,
    10:  0.617,
    12:  0.888,
    16:  1.580,
    20:  2.469,
    25:  3.853,
    28:  4.834,
    32:  6.313,
    36:  7.990,
    40:  9.865,
}


def unit_weight_kg_per_m(dia_mm: int) -> float:
    """Return unit weight for given diameter. Falls back to formula d²/162."""
    return UNIT_WEIGHT.get(dia_mm, round((dia_mm ** 2) / 162.0, 3))


# ── Bar shape codes (IS 2502) ──────────────────────────
class BarShape(str, Enum):
    STRAIGHT          = "straight"
    L_HOOK_ONE_END    = "l_hook_one_end"
    L_HOOK_BOTH_ENDS  = "l_hook_both_ends"
    U_HOOK_BOTH_ENDS  = "u_hook_both_ends"
    STIRRUP_RECT      = "stirrup_rect"
    STIRRUP_SQUAR     = "stirrup_square"
    STIRRUP_DIAMOND   = "stirrup_diamond"
    CRANKED           = "cranked"
    BENT_UP           = "bent_up"
    CUSTOM            = "custom"


# ── Hook & bend allowances (IS 2502) ──────────────────
def hook_length_std(dia: int, hook_type: str = "standard") -> float:
    """
    Standard hook length per IS 2502.
    hook_type: 'standard' (180°) = 9d + 75mm min
               '90deg'           = 8d
               '45deg'           = 4d (IS 456 col.2)
    """
    if hook_type == "180" or hook_type == "standard":
        return max(9 * dia, 75.0)
    elif hook_type == "90":
        return 8 * dia
    else:  # 45
        return 4 * dia


def bend_deduction(dia: int, angle_deg: float = 45.0) -> float:
    """Bend deduction per IS 2502 Table — angle_deg ∈ {45, 90, 135}."""
    if angle_deg <= 45:
        return 1.0 * dia
    elif angle_deg <= 90:
        return 2.0 * dia
    else:
        return 3.0 * dia


# ── Development & lap lengths (IS 456-2000) ───────────
def development_length(dia: int, fck: int = 20, fy: int = 500,
                        bond_type: str = "plain") -> float:
    """
    Ld = (fy × dia) / (4 × τbd) — IS 456 Cl.26.2
    τbd for M20, Fe500 plain = 1.4 N/mm², deformed = 1.6×1.4 = 2.24 N/mm²
    """
    if fck <= 20:  tau = 1.4
    elif fck <= 25: tau = 1.6
    elif fck <= 30: tau = 1.9
    else:           tau = 2.2
    if bond_type == "deformed":
        tau *= 1.6
    ld = (fy * dia) / (4 * tau * 1.15)   # 1.15 = partial safety factor
    return round(ld, 0)


def lap_length(dia: int, fck: int = 20, fy: int = 500,
               bond_type: str = "deformed",
               lap_zone: str = "tension") -> float:
    """
    Lap = 1.3 × Ld in tension zone, 1.0 × Ld in compression — IS 456 Cl.26.2.5
    Minimum: 300 mm or 16d for compression bars.
    """
    ld = development_length(dia, fck, fy, bond_type)
    factor = 1.3 if lap_zone == "tension" else 1.0
    raw    = ld * factor
    min_lap = max(300.0, 16.0 * dia)
    return max(round(raw, 0), min_lap)


# ── Stirrup / tie cutting length ──────────────────────
def stirrup_cutting_length(
    b: float, d: float,
    dia: int,
    cover: float = 25.0,
    shape: str = "rect",
    num_legs: int = 2,
    hook_type: str = "135",
) -> float:
    """
    Stirrup cutting length for rectangular/square closed stirrups.

    b, d : beam/column cross-section breadth and depth (mm)
    dia  : stirrup diameter (mm)
    cover: clear cover (mm)
    shape: 'rect' or 'square'
    hook_type: '90' or '135' (standard seismic hook = 135°, 10d extension)
    """
    # Inner dimensions
    inner_b = b - 2 * cover
    inner_d = d - 2 * cover
    if shape == "square":
        inner_d = inner_b

    # Perimeter for closed stirrup
    perimeter = 2 * (inner_b + inner_d)

    # Hook allowance per IS 2502 / IS 13920
    if hook_type == "135":
        hook = 2 * (10 * dia)   # two 135° hooks, 10d extension each
    else:  # 90°
        hook = 2 * hook_length_std(dia, "90")

    # Bend deduction: 4 bends at 90° for rectangular closed stirrup
    bends = 4 * bend_deduction(dia, 90)

    cutting = perimeter + hook - bends
    return round(cutting, 0)


def diamond_stirrup_cutting_length(
    b: float, d: float, dia: int, cover: float = 25.0
) -> float:
    """Cutting length for diamond (45° rotated) stirrup inside rect section."""
    inner_b = b - 2 * cover
    inner_d = d - 2 * cover
    side = math.sqrt((inner_b / 2) ** 2 + (inner_d / 2) ** 2)
    perimeter = 4 * side
    hook = 2 * (10 * dia)
    bends = 4 * bend_deduction(dia, 90)
    return round(perimeter + hook - bends, 0)


# ── Bent-up / cranked bar length ──────────────────────
def cranked_bar_extra_length(slab_thickness: float, cover: float = 15.0,
                              crank_angle: float = 45.0) -> float:
    """Extra length due to cranking (bent-up bar) in slabs."""
    d = slab_thickness - 2 * cover
    extra = (d / math.sin(math.radians(crank_angle))) - d
    return round(extra, 0)


# ── Beam main bar cutting length ──────────────────────
@dataclass
class BeamBarInput:
    """All inputs for a single beam bar layer."""
    # geometry
    clear_span_mm: float
    support_width_near_mm: float = 230.0
    support_width_far_mm:  float = 230.0
    # bar properties
    dia_mm: int = 16
    num_bars: int = 2
    # splice / hooks
    has_hook_near: bool = True
    has_hook_far:  bool = True
    hook_type: str = "standard"   # 'standard'|'90'|'180'
    splice_required: bool = False
    # design params
    fck: int   = 20
    fy:  int   = 500
    bond_type: str = "deformed"
    # source info
    source: str = "manual"


@dataclass
class BeamBarResult:
    bar_id: str = ""
    dia_mm: int = 0
    num_bars: int = 0
    cutting_length_mm: float = 0.0
    lap_length_mm: float = 0.0
    total_length_mm: float = 0.0
    unit_weight_kg_per_m: float = 0.0
    total_weight_kg: float = 0.0
    formula: str = ""
    source: str = "manual"
    status: str = "calculated"   # 'calculated'|'verify'|'missing_input'


def calc_beam_main_bar(inp: BeamBarInput, bar_id: str = "B1") -> BeamBarResult:
    """
    Cutting length = clear_span + bearing_near/2 + bearing_far/2
                   + hook_near + hook_far
                   - bend_deductions
    """
    # Anchorage into supports (half bearing width each side)
    anc_near = inp.support_width_near_mm / 2
    anc_far  = inp.support_width_far_mm  / 2

    # Hook lengths
    h_near = hook_length_std(inp.dia_mm, inp.hook_type) if inp.has_hook_near else 0.0
    h_far  = hook_length_std(inp.dia_mm, inp.hook_type) if inp.has_hook_far  else 0.0

    # Straight cutting length (no bends for main bars)
    cutting = inp.clear_span_mm + anc_near + anc_far + h_near + h_far

    # Lap if required
    lap = lap_length(inp.dia_mm, inp.fck, inp.fy, inp.bond_type) \
          if inp.splice_required else 0.0

    total_per_bar = cutting + lap
    total_all     = total_per_bar * inp.num_bars
    uw            = unit_weight_kg_per_m(inp.dia_mm)
    weight        = round(total_all / 1000.0 * uw, 3)

    formula = (
        f"CL = clear_span({inp.clear_span_mm}) + anc_near({anc_near:.0f}) "
        f"+ anc_far({anc_far:.0f}) + hook_near({h_near:.0f}) + hook_far({h_far:.0f})"
        f"{f' + lap({lap:.0f})' if lap else ''} = {cutting:.0f}"
    )

    return BeamBarResult(
        bar_id=bar_id, dia_mm=inp.dia_mm, num_bars=inp.num_bars,
        cutting_length_mm=round(cutting, 0),
        lap_length_mm=round(lap, 0),
        total_length_mm=round(total_all, 0),
        unit_weight_kg_per_m=uw,
        total_weight_kg=weight,
        formula=formula,
        source=inp.source,
        status="calculated",
    )


# ── Column main bar cutting length ────────────────────
@dataclass
class ColumnBarInput:
    storey_height_mm: float
    lap_mm: float = 0.0   # 0 = auto-calculate
    dia_mm: int = 16
    num_bars: int = 4
    cover_mm: float = 40.0
    fck: int = 20
    fy:  int = 500
    bond_type: str = "deformed"
    is_bottom_column: bool = False  # starter bars from footing
    extra_length_mm: float = 0.0   # additional projection above slab
    source: str = "manual"


@dataclass
class ColumnBarResult:
    bar_id: str = ""
    dia_mm: int = 0
    num_bars: int = 0
    cutting_length_mm: float = 0.0
    lap_length_mm: float = 0.0
    total_length_mm: float = 0.0
    unit_weight_kg_per_m: float = 0.0
    total_weight_kg: float = 0.0
    formula: str = ""
    source: str = "manual"
    status: str = "calculated"


def calc_column_main_bar(inp: ColumnBarInput, bar_id: str = "C1") -> ColumnBarResult:
    """
    Column bar CL = storey_height + lap_above_slab + extra
    Lap = 1.3×Ld (tension, per IS 456) or from drawing schedule.
    """
    auto_lap = lap_length(inp.dia_mm, inp.fck, inp.fy, inp.bond_type, "compression")
    actual_lap = inp.lap_mm if inp.lap_mm > 0 else auto_lap
    extra = inp.extra_length_mm

    cutting = inp.storey_height_mm + actual_lap + extra
    total_all = cutting * inp.num_bars
    uw = unit_weight_kg_per_m(inp.dia_mm)
    weight = round(total_all / 1000.0 * uw, 3)

    formula = (
        f"CL = storey_height({inp.storey_height_mm}) + lap({actual_lap:.0f})"
        + (f" + extra({extra:.0f})" if extra else "")
        + f" = {cutting:.0f}"
    )

    return ColumnBarResult(
        bar_id=bar_id, dia_mm=inp.dia_mm, num_bars=inp.num_bars,
        cutting_length_mm=round(cutting, 0),
        lap_length_mm=round(actual_lap, 0),
        total_length_mm=round(total_all, 0),
        unit_weight_kg_per_m=uw,
        total_weight_kg=weight,
        formula=formula,
        source=inp.source,
        status="calculated",
    )


# ── Tie / stirrup schedule ────────────────────────────
@dataclass
class StirrupInput:
    b_mm: float          # breadth
    d_mm: float          # depth
    dia_mm: int = 8
    cover_mm: float = 25.0
    spacing_mm: float = 150.0
    zone_length_mm: float = 0.0   # 0 = use full span
    clear_span_mm: float = 0.0
    shape: str = "rect"
    hook_type: str = "135"
    source: str = "manual"


@dataclass
class StirrupResult:
    bar_id: str = ""
    dia_mm: int = 0
    cutting_length_mm: float = 0.0
    num_stirrups: int = 0
    total_length_mm: float = 0.0
    unit_weight_kg_per_m: float = 0.0
    total_weight_kg: float = 0.0
    formula: str = ""
    source: str = "manual"
    status: str = "calculated"


def calc_stirrups(inp: StirrupInput, bar_id: str = "ST1") -> StirrupResult:
    cl = stirrup_cutting_length(
        inp.b_mm, inp.d_mm, inp.dia_mm,
        inp.cover_mm, inp.shape, hook_type=inp.hook_type
    )

    zone = inp.zone_length_mm if inp.zone_length_mm > 0 else inp.clear_span_mm
    if zone > 0 and inp.spacing_mm > 0:
        num = math.ceil(zone / inp.spacing_mm) + 1
    else:
        num = 0

    total = cl * num
    uw = unit_weight_kg_per_m(inp.dia_mm)
    weight = round(total / 1000.0 * uw, 3)

    formula = (
        f"Stirrup CL = 2×(b_inner+d_inner) + 2×hook - bends"
        f" = {cl:.0f} mm; "
        f"Nos = zone({zone:.0f}) / spacing({inp.spacing_mm}) + 1 = {num}"
    )

    return StirrupResult(
        bar_id=bar_id, dia_mm=inp.dia_mm,
        cutting_length_mm=cl,
        num_stirrups=num,
        total_length_mm=round(total, 0),
        unit_weight_kg_per_m=uw,
        total_weight_kg=weight,
        formula=formula,
        source=inp.source,
        status="calculated" if zone > 0 else "missing_input",
    )


# ── Slab bar cutting length ───────────────────────────
def calc_slab_bar(
    span_mm: float, support_width_mm: float = 230.0,
    dia: int = 10, fck: int = 20, fy: int = 500,
    has_hooks: bool = False, source: str = "manual"
) -> dict:
    anc = support_width_mm / 2
    hook = hook_length_std(dia) if has_hooks else 0.0
    cl   = span_mm + 2 * anc + 2 * hook
    uw   = unit_weight_kg_per_m(dia)
    return {
        "cutting_length_mm": round(cl, 0),
        "unit_weight_kg_per_m": uw,
        "formula": f"CL = span({span_mm}) + 2×anc({anc:.0f}) + 2×hook({hook:.0f}) = {cl:.0f}",
        "source": source,
        "status": "calculated",
    }


# ── Diameter-wise summary ─────────────────────────────
def diameter_summary(bar_rows: list[dict]) -> dict[int, dict]:
    """
    bar_rows: list of dicts with keys dia_mm, total_length_mm, total_weight_kg
    Returns {dia: {total_length_m, total_weight_kg, num_bars}}
    """
    summary: dict[int, dict] = {}
    for row in bar_rows:
        d = int(row.get("dia_mm", 0))
        if d <= 0:
            continue
        s = summary.setdefault(d, {"dia_mm": d, "total_length_m": 0.0,
                                    "total_weight_kg": 0.0, "num_bars": 0})
        s["total_length_m"]  += row.get("total_length_mm", 0) / 1000.0
        s["total_weight_kg"] += row.get("total_weight_kg", 0)
        s["num_bars"]        += int(row.get("num_bars", 0))
    # round
    for d in summary:
        summary[d]["total_length_m"]  = round(summary[d]["total_length_m"],  3)
        summary[d]["total_weight_kg"] = round(summary[d]["total_weight_kg"], 3)
    return summary


# ── Conflict / missing input markers ──────────────────
VERIFY   = "VERIFY_REQUIRED"
CONFLICT = "CONFLICT_DETECTED"
MISSING  = "MISSING_INPUT"


def mark_verify(reason: str) -> dict:
    return {"status": VERIFY,   "reason": reason, "value": None}

def mark_conflict(reason: str) -> dict:
    return {"status": CONFLICT, "reason": reason, "value": None}

def mark_missing(field: str) -> dict:
    return {"status": MISSING,  "reason": f"{field} not provided",  "value": None}
