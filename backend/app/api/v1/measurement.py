"""Measurement Book API — dimensional entries with formula display."""
from typing import Optional, List
from uuid import UUID
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.measurement import MeasurementBook, MeasurementItem

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class MeasurementItemOut(BaseModel):
    id: UUID
    sort_order: int
    is_heading: bool
    item_ref: Optional[str]
    description: str
    unit: Optional[str]
    length: Optional[float]
    width: Optional[float]
    height: Optional[float]
    nos: Optional[float]
    quantity: Optional[float]
    formula_display: Optional[str]
    is_manual_override: bool
    override_reason: Optional[str]
    is_deduction: bool
    deduction_ref: Optional[str]
    sor_item_id: Optional[UUID]
    notes: Optional[str]
    model_config = {"from_attributes": True}


class MeasurementItemCreate(BaseModel):
    sort_order: int = 0
    is_heading: bool = False
    item_ref: Optional[str] = None
    description: str
    unit: Optional[str] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    nos: Optional[float] = 1.0
    quantity: Optional[float] = None          # provide for manual override
    is_manual_override: bool = False
    override_reason: Optional[str] = None
    is_deduction: bool = False
    deduction_ref: Optional[str] = None
    sor_item_id: Optional[UUID] = None
    notes: Optional[str] = None


class MBOut(BaseModel):
    id: UUID
    project_id: UUID
    building_id: Optional[UUID]
    boq_id: Optional[UUID]
    mb_number: str
    title: str
    description: Optional[str]
    checked_by: Optional[str]
    date_of_measurement: Optional[datetime]
    is_approved: bool
    notes: Optional[str]
    created_at: datetime
    items: List[MeasurementItemOut] = []
    model_config = {"from_attributes": True}


class MBCreate(BaseModel):
    project_id: UUID
    building_id: Optional[UUID] = None
    boq_id: Optional[UUID] = None
    title: str = "Measurement Book"
    description: Optional[str] = None
    checked_by: Optional[str] = None
    date_of_measurement: Optional[datetime] = None
    notes: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _compute_quantity(item: MeasurementItem) -> tuple[float, str]:
    """
    Compute quantity from dimensions and generate formula string.
    Formula: Nos × L × W × H = qty  (only non-None values shown)
    """
    if item.is_heading:
        return 0.0, ""
    if item.is_manual_override and item.quantity is not None:
        return item.quantity, f"Manual: {item.quantity} {item.unit or ''}"

    parts = []
    product = 1.0
    has_dim = False

    nos = item.nos or 1.0
    if nos != 1.0:
        parts.append(f"{nos:g}")
        product *= nos
        has_dim = True

    for dim, label in [(item.length, "L"), (item.width, "W"), (item.height, "H/D")]:
        if dim is not None and dim > 0:
            parts.append(f"{dim:g}")
            product *= dim
            has_dim = True

    if not has_dim:
        return 0.0, ""

    qty = round(product, 4)
    formula = " × ".join(parts) + f" = {qty} {item.unit or ''}"

    if item.is_deduction:
        qty = -abs(qty)
        formula = f"Deduct: {formula}"

    return qty, formula


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/project/{project_id}", response_model=List[MBOut])
def list_books(project_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    books = db.query(MeasurementBook).filter(MeasurementBook.project_id == str(project_id)).all()
    return books


@router.get("/{book_id}", response_model=MBOut)
def get_book(book_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    book = db.query(MeasurementBook).filter(MeasurementBook.id == str(book_id)).first()
    if not book:
        raise HTTPException(404, "Measurement book not found")
    return book


@router.post("/", response_model=MBOut, status_code=201)
def create_book(payload: MBCreate, db: Session = Depends(get_db), cu: User = Depends(get_current_active_user)):
    count = db.query(MeasurementBook).filter(MeasurementBook.project_id == str(payload.project_id)).count()
    mb = MeasurementBook(
        **payload.model_dump(),
        mb_number=f"MB-{count+1:03d}",
        prepared_by=str(cu.id),
    )
    db.add(mb); db.commit(); db.refresh(mb)
    return mb


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    book = db.query(MeasurementBook).filter(MeasurementBook.id == str(book_id)).first()
    if not book:
        raise HTTPException(404, "Not found")
    db.delete(book); db.commit()


@router.post("/{book_id}/items", response_model=MeasurementItemOut, status_code=201)
def add_item(book_id: UUID, payload: MeasurementItemCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    book = db.query(MeasurementBook).filter(MeasurementBook.id == str(book_id)).first()
    if not book:
        raise HTTPException(404, "Book not found")

    item = MeasurementItem(book_id=str(book_id), **payload.model_dump(exclude={"sor_item_id"}))
    if payload.sor_item_id:
        item.sor_item_id = str(payload.sor_item_id)

    qty, formula = _compute_quantity(item)
    item.quantity = qty
    item.formula_display = formula

    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/{book_id}/items/{item_id}", response_model=MeasurementItemOut)
def update_item(book_id: UUID, item_id: UUID, payload: MeasurementItemCreate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    item = db.query(MeasurementItem).filter(
        MeasurementItem.id == str(item_id),
        MeasurementItem.book_id == str(book_id)
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")

    for k, v in payload.model_dump(exclude={"sor_item_id"}, exclude_unset=True).items():
        setattr(item, k, v)
    if payload.sor_item_id:
        item.sor_item_id = str(payload.sor_item_id)

    qty, formula = _compute_quantity(item)
    item.quantity = qty
    item.formula_display = formula

    db.commit(); db.refresh(item)
    return item


@router.delete("/{book_id}/items/{item_id}", status_code=204)
def delete_item(book_id: UUID, item_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    item = db.query(MeasurementItem).filter(
        MeasurementItem.id == str(item_id),
        MeasurementItem.book_id == str(book_id)
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item); db.commit()


@router.get("/{book_id}/summary")
def book_summary(book_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    """Return total quantities grouped by description/unit for BOQ linkage."""
    items = db.query(MeasurementItem).filter(
        MeasurementItem.book_id == str(book_id),
        MeasurementItem.is_heading == False
    ).all()
    groups: dict = {}
    for it in items:
        key = (it.description, it.unit or "")
        groups[key] = groups.get(key, 0.0) + (it.quantity or 0.0)
    return [{"description": k[0], "unit": k[1], "total_quantity": round(v, 4)} for k, v in groups.items()]
