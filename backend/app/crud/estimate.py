from typing import List
from sqlalchemy.orm import Session
from uuid import UUID
import json

from app.models.estimate import Estimate, WorkType

_WORK_TYPE_MAP = {
    "excavation":         (WorkType.EXCAVATION,       "m3"),
    "pcc":                (WorkType.PCC,               "m3"),
    "rcc_footing":        (WorkType.RCC_FOOTING,       "m3"),
    "rcc_column":         (WorkType.RCC_COLUMN,        "m3"),
    "rcc_beam":           (WorkType.RCC_BEAM,          "m3"),
    "rcc_slab":           (WorkType.RCC_SLAB,          "m3"),
    "brickwork_external": (WorkType.BRICKWORK,         "m3"),
    "blockwork_internal": (WorkType.BLOCKWORK,         "m3"),
    "plaster_external":   (WorkType.PLASTER_EXTERNAL,  "m2"),
    "plaster_internal":   (WorkType.PLASTER_INTERNAL,  "m2"),
    "flooring":           (WorkType.FLOORING,          "m2"),
    "paint":              (WorkType.PAINT_INTERNAL,    "m2"),
    "waterproofing":      (WorkType.WATERPROOFING,     "m2"),
}


def _wt_val(wt) -> str:
    """Always return the string value of a WorkType — works with both str and enum."""
    return wt.value if hasattr(wt, "value") else str(wt)


def _to_json(d) -> str:
    if d is None:
        return None
    if isinstance(d, str):
        return d
    try:
        return json.dumps(d)
    except Exception:
        return str(d)


def save_estimates(db: Session, project_id: UUID, building_id: UUID, engine_results: dict) -> List[Estimate]:
    saved = []

    for key, result in engine_results.items():
        if key not in _WORK_TYPE_MAP:
            continue
        work_type, unit = _WORK_TYPE_MAP[key]
        wt_str = _wt_val(work_type)
        details = result.details if hasattr(result, "details") else {}

        # Delete existing — compare using string value for SQLite compatibility
        db.query(Estimate).filter(
            Estimate.project_id == str(project_id),
            Estimate.building_id == str(building_id),
            Estimate.work_type == wt_str,
        ).delete(synchronize_session=False)

        qty = getattr(result, "volume_m3", None) or getattr(result, "area_m2", None) or 0.0
        estimate = Estimate(
            project_id=str(project_id),
            building_id=str(building_id),
            work_type=wt_str,
            quantity=round(qty, 4),
            unit=unit,
            calculation_details=_to_json(details),
            cement_bags=getattr(result, "cement_bags", 0.0) or 0.0,
            sand_cft=getattr(result, "sand_cft", 0.0) or 0.0,
            aggregate_cft=getattr(result, "aggregate_cft", 0.0) or 0.0,
            steel_kg=getattr(result, "steel_kg", 0.0) or 0.0,
            bricks_nos=getattr(result, "bricks_nos", 0.0) or 0.0,
            paint_ltr=getattr(result, "paint_litres", 0.0) or 0.0,
            tiles_sqm=getattr(result, "tiles_m2_with_wastage", 0.0) or 0.0,
        )
        db.add(estimate)
        saved.append(estimate)

    # Steel summary
    steel = engine_results.get("steel_summary")
    if steel:
        wt_str = _wt_val(WorkType.STEEL_REINFORCEMENT)
        db.query(Estimate).filter(
            Estimate.project_id == str(project_id),
            Estimate.building_id == str(building_id),
            Estimate.work_type == wt_str,
        ).delete(synchronize_session=False)
        est = Estimate(
            project_id=str(project_id),
            building_id=str(building_id),
            work_type=wt_str,
            quantity=steel.steel_kg,
            unit="kg",
            calculation_details=_to_json(steel.details),
            steel_kg=steel.steel_kg,
        )
        db.add(est)
        saved.append(est)

    # Openings
    openings = engine_results.get("openings", {})
    if openings:
        for otype, wtype in [("doors", WorkType.DOORS), ("windows", WorkType.WINDOWS)]:
            item = openings.get(otype)
            if item:
                wt_str = _wt_val(wtype)
                db.query(Estimate).filter(
                    Estimate.project_id == str(project_id),
                    Estimate.building_id == str(building_id),
                    Estimate.work_type == wt_str,
                ).delete(synchronize_session=False)
                db.add(Estimate(
                    project_id=str(project_id),
                    building_id=str(building_id),
                    work_type=wt_str,
                    quantity=item.count,
                    unit="no",
                    calculation_details=_to_json(item.details),
                ))

    db.commit()
    return saved


def get_estimates_by_project(db: Session, project_id: UUID) -> List[Estimate]:
    return db.query(Estimate).filter(Estimate.project_id == str(project_id)).all()


def get_estimates_by_building(db: Session, building_id: UUID) -> List[Estimate]:
    return db.query(Estimate).filter(Estimate.building_id == str(building_id)).all()


def get_estimate_summary(db: Session, project_id: UUID) -> dict:
    rows = get_estimates_by_project(db, project_id)
    steel_wt = _wt_val(WorkType.STEEL_REINFORCEMENT)

    summary = {
        "total_cement_bags": 0.0, "total_sand_cft": 0.0,
        "total_aggregate_cft": 0.0, "total_steel_kg": 0.0,
        "total_bricks": 0.0, "total_blocks": 0.0,
        "total_paint_ltr": 0.0, "total_tiles_sqm": 0.0,
        "total_material_cost": 0.0, "total_labour_cost": 0.0,
        "total_equipment_cost": 0.0, "grand_total_cost": 0.0,
    }

    steel_summary_kg = 0.0
    has_steel_summary = False

    for r in rows:
        wt = _wt_val(r.work_type)
        if wt == steel_wt:
            has_steel_summary = True
            steel_summary_kg = r.steel_kg or 0.0
            continue
        summary["total_cement_bags"]    += r.cement_bags or 0
        summary["total_sand_cft"]       += r.sand_cft or 0
        summary["total_aggregate_cft"]  += r.aggregate_cft or 0
        summary["total_steel_kg"]       += r.steel_kg or 0
        summary["total_bricks"]         += r.bricks_nos or 0
        summary["total_paint_ltr"]      += r.paint_ltr or 0
        summary["total_tiles_sqm"]      += r.tiles_sqm or 0
        summary["total_material_cost"]  += r.material_cost or 0
        summary["total_labour_cost"]    += r.labour_cost or 0
        summary["total_equipment_cost"] += r.equipment_cost or 0
        summary["grand_total_cost"]     += r.total_cost or 0

    # Use steel summary row if available (more accurate than sum of element rows)
    if has_steel_summary:
        summary["total_steel_kg"] = steel_summary_kg

    summary["total_steel_tons"] = round(summary["total_steel_kg"] / 1000, 3)
    return summary
