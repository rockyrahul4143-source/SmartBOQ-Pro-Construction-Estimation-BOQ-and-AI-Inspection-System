from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.crud import material as material_crud
from app.models.user import User
from app.models.material import MaterialCategory
from app.schemas.material import (
    MaterialCreate, MaterialUpdate, MaterialOut, MaterialListItem,
    MaterialRateUpdate, RateHistoryOut, RateAnalysisInput, RateAnalysisResult,
    CostEstimateInput, CostBreakdown,
)
from app.schemas.auth import MessageResponse
from app.services.rate_analysis import analyse_rate, cost_estimate_for_project
from app.crud.estimate import get_estimate_summary

router = APIRouter()


# ── List ──────────────────────────────────────────────
@router.get("/", summary="List all materials with filters")
def list_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    category: Optional[MaterialCategory] = None,
    search: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    items, total = material_crud.get_materials(db, skip, limit, category, search, active_only)
    return {
        "total": total,
        "data": [MaterialListItem.model_validate(m) for m in items],
    }


@router.get("/by-category", summary="Materials grouped by category (for dropdowns)")
def list_by_category(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    grouped = material_crud.get_materials_by_category(db)
    return {cat: [MaterialListItem.model_validate(m) for m in mats] for cat, mats in grouped.items()}


# ── Create ────────────────────────────────────────────
@router.post("/", response_model=MaterialOut, status_code=status.HTTP_201_CREATED,
             summary="Add a new material (Admin only)")
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if payload.material_code and material_crud.get_material_by_code(db, payload.material_code):
        raise HTTPException(status_code=409, detail="Material code already exists")
    return material_crud.create_material(db, payload)


# ── Get by ID ─────────────────────────────────────────
@router.get("/{material_id}", response_model=MaterialOut, summary="Get material details")
def get_material(
    material_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    m = material_crud.get_material_by_id(db, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return m


# ── Update ────────────────────────────────────────────
@router.put("/{material_id}", response_model=MaterialOut, summary="Update material (Admin only)")
def update_material(
    material_id: UUID,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    m = material_crud.get_material_by_id(db, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return material_crud.update_material(db, m, payload)


# ── Update Rate ───────────────────────────────────────
@router.patch("/{material_id}/rate", response_model=MaterialOut,
              summary="Update material rate with history tracking (Admin only)")
def update_rate(
    material_id: UUID,
    payload: MaterialRateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    m = material_crud.get_material_by_id(db, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return material_crud.update_rate(db, m, payload, current_user.id)


# ── Rate History ──────────────────────────────────────
@router.get("/{material_id}/rate-history", response_model=List[RateHistoryOut],
            summary="Get rate change history for a material")
def get_rate_history(
    material_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    m = material_crud.get_material_by_id(db, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return material_crud.get_rate_history(db, material_id)


# ── Soft Delete ───────────────────────────────────────
@router.delete("/{material_id}", response_model=MessageResponse,
               summary="Deactivate material (Admin only)")
def delete_material(
    material_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    m = material_crud.get_material_by_id(db, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    material_crud.delete_material(db, m)
    return MessageResponse(message=f"Material '{m.name}' deactivated.")


# ── Rate Analysis ─────────────────────────────────────
@router.post("/rate-analysis/calculate", response_model=RateAnalysisResult,
             summary="Calculate all-in rate for a unit of work")
def calculate_rate(
    payload: RateAnalysisInput,
    _: User = Depends(get_current_active_user),
):
    """
    Computes: Material Cost + Labour Cost + Equipment Cost + Overhead + Profit + Contingency.
    Returns a detailed breakdown suitable for BOQ rate columns.
    """
    return analyse_rate(payload)


# ── Cost Estimate for Project ─────────────────────────
@router.post("/cost-estimate/project", response_model=CostBreakdown,
             summary="Full cost estimate for a project using saved quantity estimates")
def project_cost_estimate(
    payload: CostEstimateInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    Computes project total cost from saved estimates + current material rates.
    Labour and equipment are derived as a % of material cost.
    """
    summary = get_estimate_summary(db, payload.project_id)
    material_total = summary.get("total_material_cost", 0.0)

    # If material costs not yet costed, use a flat material quantity estimate
    # multiplied by default rates. In practice, the BOQ pricing handles this.
    if material_total == 0:
        raise HTTPException(
            status_code=422,
            detail="No costed estimates found. Run BOQ pricing first or enter material totals."
        )

    breakdown = cost_estimate_for_project(
        material_cost_total=material_total,
        labour_pct=payload.labour_pct_of_material,
        equipment_pct=payload.equipment_pct_of_material,
        overhead_pct=payload.overhead_pct,
        profit_pct=payload.profit_pct,
        contingency_pct=payload.contingency_pct,
    )
    return CostBreakdown(project_id=payload.project_id, **breakdown)
