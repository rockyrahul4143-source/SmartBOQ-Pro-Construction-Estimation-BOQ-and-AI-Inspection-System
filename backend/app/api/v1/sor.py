"""SOR / Item Master API"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.sor import SORItem, WorkCategory, RateSource

router = APIRouter()


class SORItemOut(BaseModel):
    id: UUID
    item_code: str
    description: str
    specification: Optional[str] = None
    category: WorkCategory
    sub_category: Optional[str] = None
    unit: str
    basic_rate: float
    material_rate: Optional[float] = 0.0
    labour_rate: Optional[float] = 0.0
    equipment_rate: Optional[float] = 0.0
    rate_source: RateSource
    rate_year: Optional[int] = None
    formula_type: Optional[str] = None
    formula_note: Optional[str] = None
    mix_design: Optional[str] = None
    is_active: bool
    is_system: bool
    tags: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class SORItemCreate(BaseModel):
    item_code: str
    description: str
    specification: Optional[str] = None
    category: WorkCategory = WorkCategory.OTHER
    sub_category: Optional[str] = None
    unit: str
    basic_rate: float = 0.0
    material_rate: Optional[float] = 0.0
    labour_rate: Optional[float] = 0.0
    equipment_rate: Optional[float] = 0.0
    rate_source: RateSource = RateSource.CUSTOM
    rate_year: Optional[int] = None
    formula_type: Optional[str] = None
    formula_note: Optional[str] = None
    mix_design: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None


class SORItemUpdate(BaseModel):
    description: Optional[str] = None
    specification: Optional[str] = None
    category: Optional[WorkCategory] = None
    sub_category: Optional[str] = None
    unit: Optional[str] = None
    basic_rate: Optional[float] = None
    material_rate: Optional[float] = None
    labour_rate: Optional[float] = None
    equipment_rate: Optional[float] = None
    rate_source: Optional[RateSource] = None
    rate_year: Optional[int] = None
    formula_note: Optional[str] = None
    mix_design: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=dict)
def list_sor_items(
    search: Optional[str] = Query(None),
    category: Optional[WorkCategory] = Query(None),
    is_active: Optional[bool] = Query(True),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    q = db.query(SORItem)
    if is_active is not None:
        q = q.filter(SORItem.is_active == is_active)
    if category:
        q = q.filter(SORItem.category == category)
    if search:
        pat = f"%{search}%"
        q = q.filter(
            SORItem.description.ilike(pat) |
            SORItem.item_code.ilike(pat) |
            SORItem.tags.ilike(pat)
        )
    total = q.count()
    items = q.order_by(SORItem.category, SORItem.item_code).offset(skip).limit(limit).all()
    return {"total": total, "data": [SORItemOut.model_validate(i) for i in items]}


@router.get("/categories")
def list_categories(_: User = Depends(get_current_active_user)):
    return [{"value": c.value, "label": c.value.replace("_", " ").title()} for c in WorkCategory]


@router.get("/{item_id}", response_model=SORItemOut)
def get_sor_item(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    item = db.query(SORItem).filter(SORItem.id == str(item_id)).first()
    if not item:
        raise HTTPException(404, "SOR item not found")
    return item


@router.post("/", response_model=SORItemOut, status_code=201)
def create_sor_item(payload: SORItemCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    if db.query(SORItem).filter(SORItem.item_code == payload.item_code).first():
        raise HTTPException(409, f"Item code '{payload.item_code}' already exists")
    item = SORItem(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/{item_id}", response_model=SORItemOut)
def update_sor_item(item_id: UUID, payload: SORItemUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    item = db.query(SORItem).filter(SORItem.id == str(item_id)).first()
    if not item:
        raise HTTPException(404, "SOR item not found")
    if item.is_system:
        raise HTTPException(403, "System items cannot be modified")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit(); db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_sor_item(item_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    item = db.query(SORItem).filter(SORItem.id == str(item_id)).first()
    if not item:
        raise HTTPException(404, "SOR item not found")
    if item.is_system:
        raise HTTPException(403, "System items cannot be deleted")
    db.delete(item); db.commit()
