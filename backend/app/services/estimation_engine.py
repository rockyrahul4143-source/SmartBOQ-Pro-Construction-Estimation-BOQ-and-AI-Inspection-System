"""
SmartBOQ Pro — Quantity Estimation Engine
==========================================
All formulas follow IS 1200 (Method of Measurement of Building and Civil Engineering Works),
IS 456 (Plain & Reinforced Concrete), and standard Quantity Surveying practice.

Unit convention (unless noted):
  Lengths  → metres (m)
  Area     → square metres (m²)
  Volume   → cubic metres (m³)
  Weight   → kilograms (kg)
  Cement   → bags (1 bag = 50 kg)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


# ─────────────────────────────────────────────────────
# Mix-design constants (IS standard nominal mixes)
# Dry volume multiplier accounts for bulking & wastage
# ─────────────────────────────────────────────────────
DRY_VOLUME_FACTOR = 1.54   # wet concrete volume → dry ingredient volume

# Nominal mix ratios  cement : sand : aggregate (by volume)
MIX_RATIOS = {
    "M10": (1, 3, 6),
    "M15": (1, 2, 4),
    "M20": (1, 1.5, 3),
    "M25": (1, 1, 2),
    "PCC": (1, 3, 6),   # Plain Cement Concrete base
}

CEMENT_DENSITY_KG_M3 = 1440.0   # kg per m³ of loose cement
CEMENT_BAG_KG = 50.0             # kg per bag
SAND_DENSITY_KG_M3 = 1600.0
AGGREGATE_DENSITY_KG_M3 = 1500.0
STEEL_DENSITY_KG_M3 = 7850.0    # kg per m³ (for %-based reinforcement calc)

# Brickwork constants (IS 1905)
# Standard brick: 190×90×90 mm, mortar joints: 10 mm
BRICK_VOLUME_M3 = 0.001539       # volume of one brick with mortar (0.2×0.1×0.1 = 0.002 → deduct mortar)
BRICKS_PER_M3 = 500              # approx bricks per m³ of 230mm brickwork
MORTAR_RATIO_BRICKWORK = (1, 6)  # cement:sand for brick mortar

# Block (AAC / Hollow concrete block) constants  200×200×400 mm nominal
BLOCKS_PER_M3 = 12.5
MORTAR_RATIO_BLOCKWORK = (1, 4)

# Paint coverage
PAINT_COVERAGE_M2_PER_LITRE = 10.0   # per coat (primer + 2 coats = 3 applications)

# Waterproofing
WATERPROOFING_KG_PER_M2 = 1.5        # chemical waterproofing compound

# Plaster mortar (IS 2116)
PLASTER_MIX_RATIOS = {
    "external": (1, 6),  # cement:sand
    "internal": (1, 4),
}

CFT_PER_M3 = 35.3147  # 1 m³ = 35.3147 cft


@dataclass
class ExcavationResult:
    volume_m3: float
    description: str
    details: dict


@dataclass
class PCCResult:
    volume_m3: float
    cement_bags: float
    sand_cft: float
    aggregate_cft: float
    description: str
    details: dict


@dataclass
class RCCResult:
    volume_m3: float
    cement_bags: float
    sand_cft: float
    aggregate_cft: float
    steel_kg: float
    description: str
    details: dict


@dataclass
class BrickworkResult:
    volume_m3: float
    bricks_nos: float
    cement_bags: float
    sand_cft: float
    description: str
    details: dict


@dataclass
class PlasterResult:
    area_m2: float
    cement_bags: float
    sand_cft: float
    description: str
    details: dict


@dataclass
class FlooringResult:
    area_m2: float
    tiles_nos: float
    tiles_m2_with_wastage: float
    cement_bags: float
    sand_cft: float
    description: str
    details: dict


@dataclass
class PaintResult:
    area_m2: float
    paint_litres: float
    description: str
    details: dict


@dataclass
class SteelResult:
    steel_kg: float
    steel_tons: float
    description: str
    details: dict


@dataclass
class WaterproofingResult:
    area_m2: float
    compound_kg: float
    description: str
    details: dict


@dataclass
class OpeningsResult:
    count: int
    total_area_m2: float
    description: str
    details: dict


# ─────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────

def _cement_sand_agg(volume_m3: float, mix: str = "M20") -> tuple[float, float, float]:
    """
    Returns (cement_bags, sand_m3, aggregate_m3) for a given wet concrete volume.

    Formula:
        Dry volume = wet volume × 1.54
        Total parts = C + S + A
        Cement volume (m³) = (dry_volume × C/total_parts)
        Cement bags = cement_volume × 1440 / 50
        Sand (m³) = dry_volume × S/total_parts
        Aggregate (m³) = dry_volume × A/total_parts
    """
    c, s, a = MIX_RATIOS.get(mix, MIX_RATIOS["M20"])
    total = c + s + a
    dry_vol = volume_m3 * DRY_VOLUME_FACTOR

    cement_m3 = dry_vol * c / total
    cement_bags = (cement_m3 * CEMENT_DENSITY_KG_M3) / CEMENT_BAG_KG

    sand_m3 = dry_vol * s / total
    agg_m3 = dry_vol * a / total

    return round(cement_bags, 2), round(sand_m3 * CFT_PER_M3, 2), round(agg_m3 * CFT_PER_M3, 2)


def _plaster_cement_sand(area_m2: float, thickness_m: float, mix_key: str = "internal"):
    """
    Plaster material quantities.
    Dry volume = wet volume × 1.35 (less bulking than concrete)
    """
    c, s = PLASTER_MIX_RATIOS[mix_key]
    total = c + s
    wet_vol = area_m2 * thickness_m
    dry_vol = wet_vol * 1.35

    cement_m3 = dry_vol * c / total
    cement_bags = round((cement_m3 * CEMENT_DENSITY_KG_M3) / CEMENT_BAG_KG, 2)
    sand_cft = round((dry_vol * s / total) * CFT_PER_M3, 2)
    return cement_bags, sand_cft


# ─────────────────────────────────────────────────────
# 1. EXCAVATION
# ─────────────────────────────────────────────────────

def calc_excavation(
    plot_length: float,
    plot_width: float,
    depth: float,
    slope_allowance: float = 0.30,   # extra width/length for working space
) -> ExcavationResult:
    """
    Earth excavation for foundation.
    Volume = (L + 2×slope) × (W + 2×slope) × depth
    Add 30 cm working space on all sides (IS 1200 Part 1).
    """
    L = plot_length + 2 * slope_allowance
    W = plot_width + 2 * slope_allowance
    volume = round(L * W * depth, 3)

    return ExcavationResult(
        volume_m3=volume,
        description=f"Earth excavation: {L:.2f}m × {W:.2f}m × {depth:.2f}m depth",
        details={
            "net_length_m": round(L, 3),
            "net_width_m": round(W, 3),
            "depth_m": depth,
            "slope_allowance_m": slope_allowance,
            "volume_m3": volume,
            "unit": "m3",
        },
    )


# ─────────────────────────────────────────────────────
# 2. PCC (Plain Cement Concrete)
# ─────────────────────────────────────────────────────

def calc_pcc(
    length: float,
    width: float,
    thickness: float,
    mix: str = "M10",
) -> PCCResult:
    """
    PCC below footings and floor slab.
    Mix M10 (1:3:6) is standard for PCC.
    """
    volume = round(length * width * thickness, 3)
    cement_bags, sand_cft, agg_cft = _cement_sand_agg(volume, mix)

    return PCCResult(
        volume_m3=volume,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        aggregate_cft=agg_cft,
        description=f"PCC {mix}: {length:.2f}×{width:.2f}×{thickness:.3f}m",
        details={
            "length_m": length, "width_m": width, "thickness_m": thickness,
            "volume_m3": volume, "mix": mix,
            "cement_bags": cement_bags, "sand_cft": sand_cft, "aggregate_cft": agg_cft,
        },
    )


# ─────────────────────────────────────────────────────
# 3. RCC FOOTING
# ─────────────────────────────────────────────────────

def calc_rcc_footing(
    footing_length: float,
    footing_width: float,
    footing_depth: float,
    num_footings: int,
    steel_pct: float = 0.8,    # % of concrete volume
    mix: str = "M20",
) -> RCCResult:
    """
    RCC Isolated footing.
    Steel % of concrete volume (by weight): typically 0.5–1.5% for footings.
    Steel weight = volume × steel_density × (pct/100)
    """
    vol_one = footing_length * footing_width * footing_depth
    volume = round(vol_one * num_footings, 3)
    cement_bags, sand_cft, agg_cft = _cement_sand_agg(volume, mix)
    steel_kg = round(volume * STEEL_DENSITY_KG_M3 * steel_pct / 100, 2)

    return RCCResult(
        volume_m3=volume,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        aggregate_cft=agg_cft,
        steel_kg=steel_kg,
        description=f"RCC Footing {mix}: {num_footings} nos × {footing_length}×{footing_width}×{footing_depth}m",
        details={
            "num_footings": num_footings,
            "footing_length_m": footing_length, "footing_width_m": footing_width,
            "footing_depth_m": footing_depth,
            "volume_per_footing_m3": round(vol_one, 4),
            "total_volume_m3": volume, "mix": mix,
            "cement_bags": cement_bags, "sand_cft": sand_cft, "aggregate_cft": agg_cft,
            "steel_pct": steel_pct, "steel_kg": steel_kg,
        },
    )


# ─────────────────────────────────────────────────────
# 4. RCC COLUMN
# ─────────────────────────────────────────────────────

def calc_rcc_column(
    col_length: float,
    col_width: float,
    col_height: float,
    num_columns: int,
    num_floors: int = 1,
    steel_pct: float = 2.5,   # IS 456: min 0.8%, max 6%, typical 2–3%
    mix: str = "M20",
) -> RCCResult:
    """
    RCC Columns.
    Height per column = floor_height × num_floors (full building).
    """
    total_height = col_height * num_floors
    vol_one = col_length * col_width * total_height
    volume = round(vol_one * num_columns, 3)
    cement_bags, sand_cft, agg_cft = _cement_sand_agg(volume, mix)
    steel_kg = round(volume * STEEL_DENSITY_KG_M3 * steel_pct / 100, 2)

    return RCCResult(
        volume_m3=volume,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        aggregate_cft=agg_cft,
        steel_kg=steel_kg,
        description=f"RCC Column {mix}: {num_columns} nos × {col_length}×{col_width}m, {total_height:.1f}m high",
        details={
            "num_columns": num_columns, "num_floors": num_floors,
            "col_length_m": col_length, "col_width_m": col_width,
            "height_per_floor_m": col_height, "total_height_m": total_height,
            "volume_m3": volume, "mix": mix,
            "cement_bags": cement_bags, "sand_cft": sand_cft, "aggregate_cft": agg_cft,
            "steel_pct": steel_pct, "steel_kg": steel_kg,
        },
    )


# ─────────────────────────────────────────────────────
# 5. RCC BEAM
# ─────────────────────────────────────────────────────

def calc_rcc_beam(
    beam_width: float,
    beam_depth: float,
    total_beam_length: float,
    num_floors: int = 1,
    steel_pct: float = 2.0,
    mix: str = "M20",
) -> RCCResult:
    """
    RCC Beams.
    Depth used is overall beam depth (slab thickness deducted by engineer if needed).
    """
    volume = round(beam_width * beam_depth * total_beam_length * num_floors, 3)
    cement_bags, sand_cft, agg_cft = _cement_sand_agg(volume, mix)
    steel_kg = round(volume * STEEL_DENSITY_KG_M3 * steel_pct / 100, 2)

    return RCCResult(
        volume_m3=volume,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        aggregate_cft=agg_cft,
        steel_kg=steel_kg,
        description=f"RCC Beam {mix}: {beam_width}×{beam_depth}m, {total_beam_length}m total length × {num_floors} floor(s)",
        details={
            "beam_width_m": beam_width, "beam_depth_m": beam_depth,
            "total_beam_length_m": total_beam_length, "num_floors": num_floors,
            "volume_m3": volume, "mix": mix,
            "cement_bags": cement_bags, "sand_cft": sand_cft, "aggregate_cft": agg_cft,
            "steel_pct": steel_pct, "steel_kg": steel_kg,
        },
    )


# ─────────────────────────────────────────────────────
# 6. RCC SLAB
# ─────────────────────────────────────────────────────

def calc_rcc_slab(
    length: float,
    width: float,
    thickness: float,
    num_floors: int = 1,
    steel_pct: float = 1.0,   # IS 456 cl.26.5.2.1: min 0.12% to 0.15%
    mix: str = "M20",
) -> RCCResult:
    """
    RCC Roof/Floor Slab.
    Deduct column/beam volume in detailed design; here use gross slab dimensions.
    """
    volume = round(length * width * thickness * num_floors, 3)
    cement_bags, sand_cft, agg_cft = _cement_sand_agg(volume, mix)
    steel_kg = round(volume * STEEL_DENSITY_KG_M3 * steel_pct / 100, 2)

    return RCCResult(
        volume_m3=volume,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        aggregate_cft=agg_cft,
        steel_kg=steel_kg,
        description=f"RCC Slab {mix}: {length}×{width}m, {thickness*1000:.0f}mm thick × {num_floors} slab(s)",
        details={
            "length_m": length, "width_m": width, "thickness_m": thickness,
            "num_floors": num_floors, "volume_m3": volume, "mix": mix,
            "cement_bags": cement_bags, "sand_cft": sand_cft, "aggregate_cft": agg_cft,
            "steel_pct": steel_pct, "steel_kg": steel_kg,
        },
    )


# ─────────────────────────────────────────────────────
# 7. BRICKWORK
# ─────────────────────────────────────────────────────

def calc_brickwork(
    wall_length: float,
    wall_height: float,
    wall_thickness: float,         # 0.115 m (4.5") or 0.23 m (9")
    num_doors: int = 0,
    door_width: float = 0.9,
    door_height: float = 2.1,
    num_windows: int = 0,
    window_width: float = 1.2,
    window_height: float = 1.2,
    num_floors: int = 1,
    label: str = "External",
) -> BrickworkResult:
    """
    Brickwork volume deducting openings.
    Standard brick: 230×115×75 mm (IS 1905)
    500 bricks per m³ of 230mm (9-inch) wall.
    Mortar (1:6): cement bags and sand per m³.
    """
    gross_area = wall_length * wall_height * num_floors
    door_area = num_doors * door_width * door_height
    window_area = num_windows * window_width * window_height
    net_area = max(gross_area - door_area - window_area, 0)
    volume = round(net_area * wall_thickness, 3)

    bricks = round(volume * BRICKS_PER_M3, 0)

    # Mortar: ~0.30 m³ mortar per m³ of brickwork (30% void)
    mortar_vol = volume * 0.30
    c, s = MORTAR_RATIO_BRICKWORK
    total = c + s
    dry_mortar = mortar_vol * 1.35
    cement_bags = round((dry_mortar * c / total * CEMENT_DENSITY_KG_M3) / CEMENT_BAG_KG, 2)
    sand_cft = round((dry_mortar * s / total) * CFT_PER_M3, 2)

    return BrickworkResult(
        volume_m3=volume,
        bricks_nos=bricks,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        description=f"{label} Brickwork: {wall_thickness*1000:.0f}mm thick, net {net_area:.2f}m²",
        details={
            "wall_length_m": wall_length, "wall_height_m": wall_height,
            "wall_thickness_m": wall_thickness, "num_floors": num_floors,
            "gross_area_m2": round(gross_area, 3),
            "door_deduction_m2": round(door_area, 3),
            "window_deduction_m2": round(window_area, 3),
            "net_area_m2": round(net_area, 3),
            "volume_m3": volume, "bricks_nos": bricks,
            "cement_bags": cement_bags, "sand_cft": sand_cft,
        },
    )


# ─────────────────────────────────────────────────────
# 8. BLOCKWORK (AAC / Hollow Concrete Blocks)
# ─────────────────────────────────────────────────────

def calc_blockwork(
    wall_length: float,
    wall_height: float,
    wall_thickness: float = 0.20,
    num_doors: int = 0,
    door_width: float = 0.9,
    door_height: float = 2.1,
    num_windows: int = 0,
    window_width: float = 1.2,
    window_height: float = 1.2,
    num_floors: int = 1,
) -> BrickworkResult:
    """
    AAC Block (600×200×200 mm) / Hollow block walling.
    12.5 blocks per m³. Mortar (1:4).
    """
    gross_area = wall_length * wall_height * num_floors
    door_area = num_doors * door_width * door_height
    window_area = num_windows * window_width * window_height
    net_area = max(gross_area - door_area - window_area, 0)
    volume = round(net_area * wall_thickness, 3)

    blocks = round(volume * BLOCKS_PER_M3, 0)

    mortar_vol = volume * 0.20   # ~20% mortar for blocks
    c, s = MORTAR_RATIO_BLOCKWORK
    total = c + s
    dry_mortar = mortar_vol * 1.35
    cement_bags = round((dry_mortar * c / total * CEMENT_DENSITY_KG_M3) / CEMENT_BAG_KG, 2)
    sand_cft = round((dry_mortar * s / total) * CFT_PER_M3, 2)

    return BrickworkResult(
        volume_m3=volume,
        bricks_nos=blocks,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        description=f"Blockwork: {wall_thickness*1000:.0f}mm thick, net {net_area:.2f}m²",
        details={
            "wall_length_m": wall_length, "wall_height_m": wall_height,
            "wall_thickness_m": wall_thickness, "num_floors": num_floors,
            "gross_area_m2": round(gross_area, 3),
            "door_deduction_m2": round(door_area, 3),
            "window_deduction_m2": round(window_area, 3),
            "net_area_m2": round(net_area, 3),
            "volume_m3": volume, "blocks_nos": blocks,
            "cement_bags": cement_bags, "sand_cft": sand_cft,
        },
    )


# ─────────────────────────────────────────────────────
# 9. PLASTER
# ─────────────────────────────────────────────────────

def calc_plaster_external(
    wall_length: float,
    wall_height: float,
    num_floors: int = 1,
    thickness: float = 0.020,     # 20mm external plaster
    num_doors: int = 0,
    door_width: float = 0.9,
    door_height: float = 2.1,
    num_windows: int = 0,
    window_width: float = 1.2,
    window_height: float = 1.2,
) -> PlasterResult:
    gross = wall_length * wall_height * num_floors
    deduct = num_doors * door_width * door_height + num_windows * window_width * window_height
    net = round(max(gross - deduct, 0), 3)
    cement_bags, sand_cft = _plaster_cement_sand(net, thickness, "external")

    return PlasterResult(
        area_m2=net,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        description=f"External Plaster 1:6, {thickness*1000:.0f}mm, {net:.2f}m²",
        details={
            "gross_area_m2": round(gross, 3), "deduction_m2": round(deduct, 3),
            "net_area_m2": net, "thickness_m": thickness,
            "cement_bags": cement_bags, "sand_cft": sand_cft,
        },
    )


def calc_plaster_internal(
    wall_length: float,
    wall_height: float,
    num_floors: int = 1,
    thickness: float = 0.012,     # 12mm internal plaster
    num_doors: int = 0,
    door_width: float = 0.9,
    door_height: float = 2.1,
    num_windows: int = 0,
    window_width: float = 1.2,
    window_height: float = 1.2,
) -> PlasterResult:
    # Internal: both faces of internal walls + inside of external walls
    gross = wall_length * wall_height * num_floors
    deduct = num_doors * door_width * door_height + num_windows * window_width * window_height
    net = round(max(gross - deduct, 0), 3)
    cement_bags, sand_cft = _plaster_cement_sand(net, thickness, "internal")

    return PlasterResult(
        area_m2=net,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        description=f"Internal Plaster 1:4, {thickness*1000:.0f}mm, {net:.2f}m²",
        details={
            "gross_area_m2": round(gross, 3), "deduction_m2": round(deduct, 3),
            "net_area_m2": net, "thickness_m": thickness,
            "cement_bags": cement_bags, "sand_cft": sand_cft,
        },
    )


# ─────────────────────────────────────────────────────
# 10. FLOORING / TILING
# ─────────────────────────────────────────────────────

def calc_flooring(
    length: float,
    width: float,
    num_floors: int = 1,
    tile_size: float = 0.6,         # m (square tile)
    wastage_pct: float = 10.0,
) -> FlooringResult:
    """
    Floor tiling with cement-sand bedding (1:4, 25mm thick).
    Tile count includes wastage.
    """
    net_area = round(length * width * num_floors, 3)
    area_with_wastage = round(net_area * (1 + wastage_pct / 100), 3)

    tile_area_each = tile_size * tile_size
    tiles_nos = math.ceil(area_with_wastage / tile_area_each)

    # Bedding mortar (1:4, 25mm thick)
    bedding_vol = net_area * 0.025
    cement_bags, sand_cft = _plaster_cement_sand(net_area, 0.025, "internal")

    return FlooringResult(
        area_m2=net_area,
        tiles_nos=tiles_nos,
        tiles_m2_with_wastage=area_with_wastage,
        cement_bags=cement_bags,
        sand_cft=sand_cft,
        description=f"Flooring {int(tile_size*1000)}×{int(tile_size*1000)}mm tiles, {net_area:.2f}m² ({wastage_pct}% wastage)",
        details={
            "length_m": length, "width_m": width, "num_floors": num_floors,
            "net_area_m2": net_area, "tile_size_m": tile_size,
            "wastage_pct": wastage_pct, "area_with_wastage_m2": area_with_wastage,
            "tiles_nos": tiles_nos, "tile_area_m2": round(tile_area_each, 4),
            "bedding_mortar_cement_bags": cement_bags, "bedding_mortar_sand_cft": sand_cft,
        },
    )


# ─────────────────────────────────────────────────────
# 11. PAINT
# ─────────────────────────────────────────────────────

def calc_paint(
    wall_area_m2: float,
    ceiling_area_m2: float = 0.0,
    coats: int = 2,
    coverage_m2_per_litre: float = PAINT_COVERAGE_M2_PER_LITRE,
) -> PaintResult:
    """
    Paint quantity = total area / coverage per litre × number of coats.
    Add primer coat (1 coat) implicitly: coats+1.
    """
    total_area = round(wall_area_m2 + ceiling_area_m2, 3)
    litres = round(total_area * (coats + 1) / coverage_m2_per_litre, 2)   # +1 for primer

    return PaintResult(
        area_m2=total_area,
        paint_litres=litres,
        description=f"Paint: {total_area:.2f}m², {coats} finish coats + 1 primer = {coats+1} total",
        details={
            "wall_area_m2": wall_area_m2, "ceiling_area_m2": ceiling_area_m2,
            "total_area_m2": total_area, "coats": coats,
            "coverage_m2_per_litre": coverage_m2_per_litre,
            "paint_litres": litres,
        },
    )


# ─────────────────────────────────────────────────────
# 12. STEEL REINFORCEMENT (standalone, used for summary)
# ─────────────────────────────────────────────────────

def calc_total_steel(
    slab_vol_m3: float, slab_pct: float = 1.0,
    column_vol_m3: float = 0, column_pct: float = 2.5,
    beam_vol_m3: float = 0, beam_pct: float = 2.0,
    footing_vol_m3: float = 0, footing_pct: float = 0.8,
) -> SteelResult:
    """Total reinforcement steel across all RCC elements."""
    steel_kg = (
        slab_vol_m3 * STEEL_DENSITY_KG_M3 * slab_pct / 100
        + column_vol_m3 * STEEL_DENSITY_KG_M3 * column_pct / 100
        + beam_vol_m3 * STEEL_DENSITY_KG_M3 * beam_pct / 100
        + footing_vol_m3 * STEEL_DENSITY_KG_M3 * footing_pct / 100
    )
    steel_kg = round(steel_kg, 2)
    return SteelResult(
        steel_kg=steel_kg,
        steel_tons=round(steel_kg / 1000, 3),
        description=f"Total reinforcement steel: {steel_kg:.2f} kg ({steel_kg/1000:.3f} tons)",
        details={
            "slab_steel_kg": round(slab_vol_m3 * STEEL_DENSITY_KG_M3 * slab_pct / 100, 2),
            "column_steel_kg": round(column_vol_m3 * STEEL_DENSITY_KG_M3 * column_pct / 100, 2),
            "beam_steel_kg": round(beam_vol_m3 * STEEL_DENSITY_KG_M3 * beam_pct / 100, 2),
            "footing_steel_kg": round(footing_vol_m3 * STEEL_DENSITY_KG_M3 * footing_pct / 100, 2),
            "total_kg": steel_kg, "total_tons": round(steel_kg / 1000, 3),
        },
    )


# ─────────────────────────────────────────────────────
# 13. WATERPROOFING
# ─────────────────────────────────────────────────────

def calc_waterproofing(area_m2: float) -> WaterproofingResult:
    """
    Chemical waterproofing treatment (e.g. Dr. Fixit / Integral compound).
    Rate: 1.5 kg/m² for two-coat application.
    """
    compound_kg = round(area_m2 * WATERPROOFING_KG_PER_M2, 2)
    return WaterproofingResult(
        area_m2=area_m2,
        compound_kg=compound_kg,
        description=f"Waterproofing: {area_m2:.2f}m², {compound_kg:.2f}kg compound",
        details={"area_m2": area_m2, "rate_kg_per_m2": WATERPROOFING_KG_PER_M2, "compound_kg": compound_kg},
    )


# ─────────────────────────────────────────────────────
# 14. DOORS & WINDOWS
# ─────────────────────────────────────────────────────

def calc_openings(
    num_doors: int, door_width: float, door_height: float,
    num_windows: int, window_width: float, window_height: float,
) -> dict:
    door_area = round(num_doors * door_width * door_height, 3)
    window_area = round(num_windows * window_width * window_height, 3)
    return {
        "doors": OpeningsResult(
            count=num_doors, total_area_m2=door_area,
            description=f"{num_doors} doors, {door_width}×{door_height}m each = {door_area:.2f}m²",
            details={"count": num_doors, "width_m": door_width, "height_m": door_height, "total_area_m2": door_area},
        ),
        "windows": OpeningsResult(
            count=num_windows, total_area_m2=window_area,
            description=f"{num_windows} windows, {window_width}×{window_height}m each = {window_area:.2f}m²",
            details={"count": num_windows, "width_m": window_width, "height_m": window_height, "total_area_m2": window_area},
        ),
    }


# ─────────────────────────────────────────────────────
# MASTER ESTIMATOR — runs all calculations for a Building
# ─────────────────────────────────────────────────────

def run_full_estimation(building) -> dict:
    """
    Accepts a Building ORM object and returns a structured dict
    with all quantity estimates, material summaries and totals.
    """
    b = building
    results = {}

    # Defaults for safety
    pl = b.plot_length or 0
    pw = b.plot_width or 0
    nf = b.num_floors or 1

    # 1. Excavation
    if pl and pw and b.excavation_depth:
        results["excavation"] = calc_excavation(pl, pw, b.excavation_depth)

    # 2. PCC
    if pl and pw and b.pcc_thickness:
        results["pcc"] = calc_pcc(pl, pw, b.pcc_thickness)

    # 3. RCC Footing
    if b.num_footings and b.num_footings > 0:
        results["rcc_footing"] = calc_rcc_footing(
            b.footing_length or 1.2,
            b.footing_width or 1.2,
            b.footing_depth or 0.3,
            b.num_footings,
            steel_pct=b.steel_percentage_column or 0.8,
        )

    # 4. RCC Columns
    if b.num_columns and b.num_columns > 0:
        results["rcc_column"] = calc_rcc_column(
            b.column_length or 0.3,
            b.column_width or 0.3,
            b.floor_height or 3.0,
            b.num_columns,
            num_floors=nf,
            steel_pct=b.steel_percentage_column or 2.5,
        )

    # 5. RCC Beams
    if b.total_beam_length and b.total_beam_length > 0:
        results["rcc_beam"] = calc_rcc_beam(
            b.beam_width or 0.23,
            b.beam_depth or 0.45,
            b.total_beam_length,
            num_floors=nf,
            steel_pct=b.steel_percentage_beam or 2.0,
        )

    # 6. RCC Slab
    sl = b.slab_length or pl
    sw = b.slab_width or pw
    if sl and sw and b.slab_thickness:
        results["rcc_slab"] = calc_rcc_slab(
            sl, sw, b.slab_thickness, num_floors=nf,
            steel_pct=b.steel_percentage_slab or 1.0,
        )

    # 7. External Brickwork
    ext_wl = b.total_external_wall_length or 0
    if ext_wl > 0:
        results["brickwork_external"] = calc_brickwork(
            ext_wl, b.wall_height or 3.0,
            b.wall_thickness_external or 0.23,
            num_doors=b.num_doors or 0, door_width=b.door_width or 0.9, door_height=b.door_height or 2.1,
            num_windows=b.num_windows or 0, window_width=b.window_width or 1.2, window_height=b.window_height or 1.2,
            num_floors=nf, label="External",
        )

    # 8. Internal Brickwork / Blockwork
    int_wl = b.total_internal_wall_length or 0
    if int_wl > 0:
        results["blockwork_internal"] = calc_blockwork(
            int_wl, b.wall_height or 3.0,
            b.wall_thickness_internal or 0.115,
            num_floors=nf,
        )

    # 9. External Plaster
    if ext_wl > 0:
        results["plaster_external"] = calc_plaster_external(
            ext_wl, b.wall_height or 3.0, num_floors=nf,
            thickness=b.plaster_thickness_external or 0.020,
            num_doors=b.num_doors or 0, door_width=b.door_width or 0.9, door_height=b.door_height or 2.1,
            num_windows=b.num_windows or 0, window_width=b.window_width or 1.2, window_height=b.window_height or 1.2,
        )

    # 10. Internal Plaster (both faces of internal walls + inner face of external)
    total_plaster_length = ext_wl + (2 * int_wl)
    if total_plaster_length > 0:
        results["plaster_internal"] = calc_plaster_internal(
            total_plaster_length, b.wall_height or 3.0, num_floors=nf,
            thickness=b.plaster_thickness_internal or 0.012,
        )

    # 11. Flooring
    if sl and sw:
        results["flooring"] = calc_flooring(
            sl, sw, num_floors=nf,
            tile_size=b.tile_size or 0.6,
            wastage_pct=b.tile_wastage_pct or 10.0,
        )

    # 12. Paint
    total_wall_area = (ext_wl + 2 * int_wl) * (b.wall_height or 3.0) * nf
    ceiling_area = (sl or pl) * (sw or pw) * nf if sl and sw else 0
    if total_wall_area > 0:
        results["paint"] = calc_paint(
            total_wall_area, ceiling_area, coats=b.paint_coats or 2
        )

    # 13. Waterproofing
    wpa = b.waterproofing_area or 0
    if wpa > 0:
        results["waterproofing"] = calc_waterproofing(wpa)

    # 14. Doors & Windows
    results["openings"] = calc_openings(
        b.num_doors or 0, b.door_width or 0.9, b.door_height or 2.1,
        b.num_windows or 0, b.window_width or 1.2, b.window_height or 1.2,
    )

    # 15. Steel summary
    slab_vol = results.get("rcc_slab", None)
    col_vol = results.get("rcc_column", None)
    beam_vol = results.get("rcc_beam", None)
    ftp_vol = results.get("rcc_footing", None)
    results["steel_summary"] = calc_total_steel(
        slab_vol_m3=slab_vol.volume_m3 if slab_vol else 0,
        slab_pct=b.steel_percentage_slab or 1.0,
        column_vol_m3=col_vol.volume_m3 if col_vol else 0,
        column_pct=b.steel_percentage_column or 2.5,
        beam_vol_m3=beam_vol.volume_m3 if beam_vol else 0,
        beam_pct=b.steel_percentage_beam or 2.0,
        footing_vol_m3=ftp_vol.volume_m3 if ftp_vol else 0,
        footing_pct=0.8,
    )

    return results
