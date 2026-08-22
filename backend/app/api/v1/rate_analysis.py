"""Rate Analysis API — material/labour/equipment breakdown per BOQ item."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.rate_analysis import RateAnalysis, RateComponent

router = APIRouter()


class ComponentOut(BaseModel):
    id: UUID
    component_type: str
    description: str
    unit: str
    quantity: float
    rate: float
    amount: float
    sort_order: float
    material_id: Optional[UUID]
    model_config = {"from_attributes": True}


class ComponentCreate(BaseModel):
    component_type: str   # "material" | "labour" | "equipment"
    description: str
    unit: str
    quantity: float = 0.0
    rate: float = 0.0
    sort_order: float = 0.0
    material_id: Optional[UUID] = None


class RAOut(BaseModel):
    id: UUID
    sor_item_id: UUID
    project_id: Optional[UUID]
    title: str
    unit: str
    material_total: float
    labour_total: float
    equipment_total: float
    direct_cost: float
    wastage_pct: float
    wastage_amount: float
    overhead_pct: float
    overhead_amount: float
    profit_pct: float
    profit_amount: float
    final_rate: float
    is_template: bool
    notes: Optional[str]
    components: List[ComponentOut] = []
    created_at: datetime
    model_config = {"from_attributes": True}


class RACreate(BaseModel):
    sor_item_id: UUID
    project_id: Optional[UUID] = None
    title: str
    unit: str
    wastage_pct: float = 5.0
    overhead_pct: float = 10.0
    profit_pct: float = 10.0
    is_template: bool = False
    notes: Optional[str] = None


def _recalc(ra: RateAnalysis, db: Session):
    """Recompute all totals from components."""
    mat = sum(c.amount for c in ra.components if c.component_type == "material")
    lab = sum(c.amount for c in ra.components if c.component_type == "labour")
    eqp = sum(c.amount for c in ra.components if c.component_type == "equipment")
    direct = mat + lab + eqp
    wastage = round(direct * ra.wastage_pct / 100, 2)
    overhead = round(direct * ra.overhead_pct / 100, 2)
    profit = round(direct * ra.profit_pct / 100, 2)
    final = round(direct + wastage + overhead + profit, 2)

    ra.material_total = round(mat, 2)
    ra.labour_total   = round(lab, 2)
    ra.equipment_total= round(eqp, 2)
    ra.direct_cost    = round(direct, 2)
    ra.wastage_amount = wastage
    ra.overhead_amount= overhead
    ra.profit_amount  = profit
    ra.final_rate     = final
    db.commit(); db.refresh(ra)


@router.get("/sor/{sor_item_id}", response_model=List[RAOut])
def list_by_sor(sor_item_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return db.query(RateAnalysis).filter(RateAnalysis.sor_item_id == str(sor_item_id)).all()


@router.get("/project/{project_id}", response_model=List[RAOut])
def list_by_project(project_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return db.query(RateAnalysis).filter(RateAnalysis.project_id == str(project_id)).all()


@router.get("/{ra_id}", response_model=RAOut)
def get_ra(ra_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra = db.query(RateAnalysis).filter(RateAnalysis.id == str(ra_id)).first()
    if not ra:
        raise HTTPException(404, "Rate analysis not found")
    return ra


@router.post("/", response_model=RAOut, status_code=201)
def create_ra(payload: RACreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra = RateAnalysis(**{
        **payload.model_dump(),
        "sor_item_id": str(payload.sor_item_id),
        "project_id": str(payload.project_id) if payload.project_id else None,
    })
    db.add(ra); db.commit(); db.refresh(ra)
    return ra


@router.put("/{ra_id}", response_model=RAOut)
def update_ra(ra_id: UUID, payload: dict, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra = db.query(RateAnalysis).filter(RateAnalysis.id == str(ra_id)).first()
    if not ra:
        raise HTTPException(404, "Not found")
    for k, v in payload.items():
        if hasattr(ra, k):
            setattr(ra, k, v)
    _recalc(ra, db)
    return ra


@router.delete("/{ra_id}", status_code=204)
def delete_ra(ra_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra = db.query(RateAnalysis).filter(RateAnalysis.id == str(ra_id)).first()
    if not ra:
        raise HTTPException(404, "Not found")
    db.delete(ra); db.commit()


@router.post("/{ra_id}/components", response_model=ComponentOut, status_code=201)
def add_component(ra_id: UUID, payload: ComponentCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra = db.query(RateAnalysis).filter(RateAnalysis.id == str(ra_id)).first()
    if not ra:
        raise HTTPException(404, "Rate analysis not found")
    comp = RateComponent(
        analysis_id=str(ra_id),
        material_id=str(payload.material_id) if payload.material_id else None,
        **{k: v for k, v in payload.model_dump(exclude={"material_id"}).items()},
        amount=round(payload.quantity * payload.rate, 2),
    )
    db.add(comp); db.commit()
    _recalc(ra, db)
    db.refresh(comp)
    return comp


@router.put("/{ra_id}/components/{comp_id}", response_model=ComponentOut)
def update_component(ra_id: UUID, comp_id: UUID, payload: ComponentCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra   = db.query(RateAnalysis).filter(RateAnalysis.id == str(ra_id)).first()
    comp = db.query(RateComponent).filter(RateComponent.id == str(comp_id), RateComponent.analysis_id == str(ra_id)).first()
    if not ra or not comp:
        raise HTTPException(404, "Not found")
    for k, v in payload.model_dump(exclude={"material_id"}, exclude_unset=True).items():
        setattr(comp, k, v)
    if payload.material_id:
        comp.material_id = str(payload.material_id)
    comp.amount = round(comp.quantity * comp.rate, 2)
    db.commit()
    _recalc(ra, db)
    db.refresh(comp)
    return comp


@router.delete("/{ra_id}/components/{comp_id}", status_code=204)
def delete_component(ra_id: UUID, comp_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    ra   = db.query(RateAnalysis).filter(RateAnalysis.id == str(ra_id)).first()
    comp = db.query(RateComponent).filter(RateComponent.id == str(comp_id)).first()
    if not ra or not comp:
        raise HTTPException(404, "Not found")
    db.delete(comp); db.commit()
    _recalc(ra, db)
