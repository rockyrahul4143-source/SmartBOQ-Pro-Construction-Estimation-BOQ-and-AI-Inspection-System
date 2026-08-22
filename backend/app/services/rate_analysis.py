"""
Rate Analysis Engine
====================
Computes the all-inclusive rate for any unit of construction work by breaking
down costs into: Material + Labour + Equipment + Overhead + Profit + Contingency.

This follows standard QS practice (FIDIC / NEC / CPWD DSR conventions).
"""
from __future__ import annotations
from typing import Optional
from app.schemas.material import RateAnalysisInput, RateAnalysisResult


def analyse_rate(payload: RateAnalysisInput) -> RateAnalysisResult:
    """
    All-in rate for one unit of construction work.

    Example — 1 m³ of M20 RCC:
      material_quantity = 8 bags cement @ 900 + 0.42 m³ sand @ 2200 + 0.84 m³ agg @ 1800
      (call this endpoint once per material component and sum, or pass blended rate)
    """
    material_cost = round(payload.material_quantity * payload.material_rate, 2)

    # Labour: skilled + helper man-days
    skilled_cost = round(payload.labour_quantity * payload.labour_rate, 2)
    helper_cost  = round(payload.helper_quantity * payload.helper_rate, 2)
    labour_cost  = round(skilled_cost + helper_cost, 2)

    equipment_cost = round(payload.equipment_rate, 2)
    direct_cost    = round(material_cost + labour_cost + equipment_cost, 2)

    overhead_amount    = round(direct_cost * payload.overhead_pct / 100, 2)
    profit_amount      = round(direct_cost * payload.profit_pct / 100, 2)
    contingency_amount = round(direct_cost * payload.contingency_pct / 100, 2)
    total_rate         = round(direct_cost + overhead_amount + profit_amount + contingency_amount, 2)

    return RateAnalysisResult(
        work_description=payload.work_description,
        unit=payload.unit,
        material_cost=material_cost,
        labour_cost=labour_cost,
        equipment_cost=equipment_cost,
        direct_cost=direct_cost,
        overhead_amount=overhead_amount,
        profit_amount=profit_amount,
        contingency_amount=contingency_amount,
        total_rate=total_rate,
        breakdown={
            "material": {
                "name": payload.material_name,
                "quantity": payload.material_quantity,
                "rate_per_unit": payload.material_rate,
                "cost": material_cost,
            },
            "labour": {
                "description": payload.labour_description,
                "skilled_days": payload.labour_quantity,
                "skilled_rate": payload.labour_rate,
                "helper_days": payload.helper_quantity,
                "helper_rate": payload.helper_rate,
                "cost": labour_cost,
            },
            "equipment": {
                "description": payload.equipment_description or "N/A",
                "cost": equipment_cost,
            },
            "direct_cost": direct_cost,
            "overhead": {"pct": payload.overhead_pct, "amount": overhead_amount},
            "profit":   {"pct": payload.profit_pct,   "amount": profit_amount},
            "contingency": {"pct": payload.contingency_pct, "amount": contingency_amount},
            "total_rate_per_unit": total_rate,
        },
    )


# ── Standard rate schedules (INR, India 2024) ────────────────────────────────
# Sources: CPWD DSR 2024, NBO India, state PWD schedules
STANDARD_LABOUR_RATES = {
    "mason":              800,    # INR/day (Class I Mason)
    "helper":             500,    # INR/day (Unskilled Labour)
    "carpenter":          900,    # INR/day
    "steel_fixer":        950,    # INR/day (Bar Bender / Fixer)
    "painter":            750,    # INR/day
    "plumber":            900,    # INR/day
    "electrician":        950,    # INR/day
    "tile_fixer":         850,    # INR/day
    "excavation_daily":   500,    # INR/day (manual excavation)
    "supervisor":         1200,   # INR/day
}

STANDARD_EQUIPMENT_RATES = {
    "concrete_mixer_per_day":    1500,   # INR/day (0.2 m³ mixer)
    "needle_vibrator_per_day":    800,   # INR/day
    "scaffolding_per_m2":          60,   # INR/m²/month
    "shuttering_per_m2":          180,   # INR/m² (steel formwork)
    "tower_crane_per_hour":      4500,   # INR/hour
    "excavator_per_hour":        1800,   # INR/hour (0.3 m³ JCB)
    "road_roller_per_hour":      2000,   # INR/hour
    "water_tanker_per_trip":      800,   # INR/trip
    "truck_per_trip":            1200,   # INR/trip (tipper 5T)
}


def cost_estimate_for_project(
    material_cost_total: float,
    labour_pct: float = 35.0,
    equipment_pct: float = 10.0,
    overhead_pct: float = 10.0,
    profit_pct: float = 10.0,
    contingency_pct: float = 5.0,
) -> dict:
    """
    High-level cost estimate from material cost total using percentage-based
    labour and equipment factors (standard QS practice for preliminary estimates).
    """
    labour    = round(material_cost_total * labour_pct / 100, 2)
    equipment = round(material_cost_total * equipment_pct / 100, 2)
    direct    = round(material_cost_total + labour + equipment, 2)
    overhead  = round(direct * overhead_pct / 100, 2)
    profit    = round(direct * profit_pct / 100, 2)
    contingency = round(direct * contingency_pct / 100, 2)
    grand_total = round(direct + overhead + profit + contingency, 2)

    return {
        "material_cost": material_cost_total,
        "labour_cost": labour,
        "equipment_cost": equipment,
        "direct_cost": direct,
        "overhead_pct": overhead_pct,  "overhead_amount": overhead,
        "profit_pct": profit_pct,      "profit_amount": profit,
        "contingency_pct": contingency_pct, "contingency_amount": contingency,
        "grand_total": grand_total,
    }
