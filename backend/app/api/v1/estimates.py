from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.crud import estimate as estimate_crud
from app.crud import building as building_crud
from app.crud import project as project_crud
from app.services import estimation_engine as eng
from app.models.user import User
from app.schemas.estimate import EstimateOut, EstimateSummary, FullEstimationResult

router = APIRouter()


def _get_building_or_404(db, building_id):
    b = building_crud.get_building_by_id(db, building_id)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    return b


def _get_project_or_404(db, project_id):
    p = project_crud.get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return p


# ─── Run full estimation for a building ──────────────
@router.post("/run/{building_id}", summary="Run quantity estimation engine for a building")
def run_estimation(
    building_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Executes all 14 civil engineering quantity calculations for the given building,
    persists results to the database, and returns full breakdown.
    """
    building = _get_building_or_404(db, building_id)
    project = _get_project_or_404(db, building.project_id)

    # Run the estimation engine
    engine_results = eng.run_full_estimation(building)

    # Persist to DB
    saved = estimate_crud.save_estimates(db, project.id, building_id, engine_results)

    # Build serialisable response
    serialised = {}
    for key, result in engine_results.items():
        if key == "openings":
            serialised[key] = {
                "doors": result["doors"].details,
                "windows": result["windows"].details,
            }
        elif hasattr(result, "details"):
            serialised[key] = {
                "description": result.description,
                **result.details,
            }

    summary_data = estimate_crud.get_estimate_summary(db, project.id)

    return {
        "project_id": str(project.id),
        "building_id": str(building_id),
        "results": serialised,
        "summary": {
            "project_id": str(project.id),
            "building_id": str(building_id),
            **summary_data,
            "items": [EstimateOut.model_validate(e) for e in saved],
        },
    }


# ─── Get saved estimates for a project ───────────────
@router.get("/project/{project_id}", response_model=List[EstimateOut],
            summary="Get all saved estimates for a project")
def get_estimates(
    project_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_project_or_404(db, project_id)
    return estimate_crud.get_estimates_by_project(db, project_id)


# ─── Get estimates for a specific building ────────────
@router.get("/building/{building_id}", response_model=List[EstimateOut],
            summary="Get estimates for a specific building")
def get_estimates_by_building(
    building_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_building_or_404(db, building_id)
    return estimate_crud.get_estimates_by_building(db, building_id)


# ─── Summary / material totals ────────────────────────
@router.get("/summary/{project_id}", summary="Aggregated material quantities for a project")
def get_summary(
    project_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_project_or_404(db, project_id)
    summary = estimate_crud.get_estimate_summary(db, project_id)
    return {"project_id": str(project_id), **summary}


# ─── Individual calculation endpoints (live, no save) ─
@router.post("/calculate/excavation", summary="Calculate excavation quantity")
def calc_excavation(
    plot_length: float, plot_width: float, depth: float,
    slope_allowance: float = 0.30,
    _: User = Depends(get_current_active_user),
):
    result = eng.calc_excavation(plot_length, plot_width, depth, slope_allowance)
    return result.details


@router.post("/calculate/pcc", summary="Calculate PCC quantity")
def calc_pcc(
    length: float, width: float, thickness: float, mix: str = "M10",
    _: User = Depends(get_current_active_user),
):
    result = eng.calc_pcc(length, width, thickness, mix)
    return result.details


@router.post("/calculate/rcc-slab", summary="Calculate RCC slab quantity")
def calc_slab(
    length: float, width: float, thickness: float = 0.125,
    num_floors: int = 1, steel_pct: float = 1.0, mix: str = "M20",
    _: User = Depends(get_current_active_user),
):
    result = eng.calc_rcc_slab(length, width, thickness, num_floors, steel_pct, mix)
    return result.details


@router.post("/calculate/brickwork", summary="Calculate brickwork quantity")
def calc_brickwork(
    wall_length: float, wall_height: float, wall_thickness: float = 0.23,
    num_doors: int = 0, door_width: float = 0.9, door_height: float = 2.1,
    num_windows: int = 0, window_width: float = 1.2, window_height: float = 1.2,
    num_floors: int = 1,
    _: User = Depends(get_current_active_user),
):
    result = eng.calc_brickwork(
        wall_length, wall_height, wall_thickness,
        num_doors, door_width, door_height,
        num_windows, window_width, window_height, num_floors,
    )
    return result.details


@router.post("/calculate/plaster", summary="Calculate plaster quantity")
def calc_plaster(
    wall_length: float, wall_height: float, thickness: float = 0.012,
    plaster_type: str = "internal", num_floors: int = 1,
    _: User = Depends(get_current_active_user),
):
    if plaster_type == "external":
        result = eng.calc_plaster_external(wall_length, wall_height, num_floors, thickness)
    else:
        result = eng.calc_plaster_internal(wall_length, wall_height, num_floors, thickness)
    return result.details


@router.post("/calculate/flooring", summary="Calculate flooring/tiling quantity")
def calc_flooring(
    length: float, width: float, num_floors: int = 1,
    tile_size: float = 0.6, wastage_pct: float = 10.0,
    _: User = Depends(get_current_active_user),
):
    result = eng.calc_flooring(length, width, num_floors, tile_size, wastage_pct)
    return result.details


@router.post("/calculate/paint", summary="Calculate paint quantity")
def calc_paint(
    wall_area_m2: float, ceiling_area_m2: float = 0.0, coats: int = 2,
    _: User = Depends(get_current_active_user),
):
    result = eng.calc_paint(wall_area_m2, ceiling_area_m2, coats)
    return result.details
