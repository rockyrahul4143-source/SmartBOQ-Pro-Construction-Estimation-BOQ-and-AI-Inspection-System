"""RA Billing API — Running Account bills against BOQ."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.billing import RABill, RABillItem, BillStatus
from app.models.boq import BOQ, BOQItem

router = APIRouter()


class BillItemOut(BaseModel):
    id: UUID
    item_no: str
    description: str
    unit: str
    rate: float
    boq_quantity: float
    previous_quantity: float
    current_quantity: float
    cumulative_quantity: float
    balance_quantity: float
    current_amount: float
    cumulative_amount: float
    previous_amount: float
    is_heading: bool
    remarks: Optional[str]
    boq_item_id: Optional[UUID]
    model_config = {"from_attributes": True}


class BillOut(BaseModel):
    id: UUID
    project_id: UUID
    boq_id: UUID
    bill_number: str
    bill_date: Optional[datetime]
    period_from: Optional[datetime]
    period_to: Optional[datetime]
    status: str
    contractor_name: Optional[str]
    current_amount: float
    cumulative_amount: float
    previous_amount: float
    deductions: float
    net_payable: float
    allow_excess: bool
    notes: Optional[str]
    created_at: datetime
    items: List[BillItemOut] = []
    model_config = {"from_attributes": True}


class BillCreate(BaseModel):
    project_id: UUID
    boq_id: UUID
    bill_date: Optional[datetime] = None
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None
    contractor_name: Optional[str] = None
    deductions: float = 0.0
    allow_excess: bool = False
    notes: Optional[str] = None


class BillItemUpdate(BaseModel):
    current_quantity: float


def _recalc_bill(bill: RABill, db: Session):
    """Recalculate bill totals from items."""
    current = sum(i.current_amount for i in bill.items if not i.is_heading)
    cumulative = sum(i.cumulative_amount for i in bill.items if not i.is_heading)
    previous = sum(i.previous_amount for i in bill.items if not i.is_heading)
    bill.current_amount    = round(current, 2)
    bill.cumulative_amount = round(cumulative, 2)
    bill.previous_amount   = round(previous, 2)
    bill.net_payable       = round(current - bill.deductions, 2)
    db.commit(); db.refresh(bill)


@router.get("/project/{project_id}", response_model=List[BillOut])
def list_bills(project_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return db.query(RABill).filter(RABill.project_id == str(project_id)).order_by(RABill.created_at.desc()).all()


@router.get("/{bill_id}", response_model=BillOut)
def get_bill(bill_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    bill = db.query(RABill).filter(RABill.id == str(bill_id)).first()
    if not bill:
        raise HTTPException(404, "Bill not found")
    return bill


@router.post("/", response_model=BillOut, status_code=201)
def create_bill(payload: BillCreate, db: Session = Depends(get_db), cu: User = Depends(get_current_active_user)):
    boq = db.query(BOQ).filter(BOQ.id == str(payload.boq_id)).first()
    if not boq:
        raise HTTPException(404, "BOQ not found")

    # Determine bill number and previous bill
    existing_bills = db.query(RABill).filter(
        RABill.project_id == str(payload.project_id),
        RABill.boq_id == str(payload.boq_id)
    ).order_by(RABill.created_at.desc()).all()

    bill_num = f"RA-{len(existing_bills)+1:03d}"
    prev_bill = existing_bills[0] if existing_bills else None

    # Build previous cumulative qty map from last bill
    prev_cumulative: dict = {}
    if prev_bill:
        for pi in prev_bill.items:
            if pi.boq_item_id:
                prev_cumulative[str(pi.boq_item_id)] = pi.cumulative_quantity

    bill = RABill(
        project_id=str(payload.project_id),
        boq_id=str(payload.boq_id),
        bill_number=bill_num,
        bill_date=payload.bill_date,
        period_from=payload.period_from,
        period_to=payload.period_to,
        contractor_name=payload.contractor_name,
        deductions=payload.deductions,
        allow_excess=payload.allow_excess,
        notes=payload.notes,
        prepared_by=str(cu.id),
        status=BillStatus.DRAFT,
    )
    db.add(bill); db.flush()

    # Create bill items from BOQ items with zero current qty
    for boq_item in sorted(boq.items, key=lambda x: x.item_no):
        prev_qty = prev_cumulative.get(str(boq_item.id), 0.0)
        item = RABillItem(
            bill_id=str(bill.id),
            boq_item_id=str(boq_item.id),
            item_no=boq_item.item_no,
            description=boq_item.description,
            unit=boq_item.unit,
            rate=boq_item.rate,
            boq_quantity=boq_item.quantity,
            previous_quantity=prev_qty,
            current_quantity=0.0,
            cumulative_quantity=prev_qty,
            balance_quantity=max(boq_item.quantity - prev_qty, 0),
            current_amount=0.0,
            cumulative_amount=round(prev_qty * boq_item.rate, 2),
            previous_amount=round(prev_qty * boq_item.rate, 2),
            is_heading=boq_item.is_heading,
        )
        db.add(item)

    db.commit(); db.refresh(bill)
    _recalc_bill(bill, db)
    return bill


@router.put("/{bill_id}/items/{item_id}", response_model=BillItemOut)
def update_bill_item(bill_id: UUID, item_id: UUID, payload: BillItemUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    bill = db.query(RABill).filter(RABill.id == str(bill_id)).first()
    item = db.query(RABillItem).filter(RABillItem.id == str(item_id), RABillItem.bill_id == str(bill_id)).first()
    if not bill or not item:
        raise HTTPException(404, "Not found")
    if bill.status in (BillStatus.CERTIFIED, BillStatus.PAID):
        raise HTTPException(403, "Cannot edit certified/paid bill")

    new_cumulative = item.previous_quantity + payload.current_quantity
    if not bill.allow_excess and new_cumulative > item.boq_quantity + 0.0001:
        raise HTTPException(422, f"Cumulative qty ({new_cumulative:.3f}) exceeds BOQ qty ({item.boq_quantity:.3f}). Enable 'allow excess' to override.")

    item.current_quantity    = round(payload.current_quantity, 4)
    item.cumulative_quantity = round(new_cumulative, 4)
    item.balance_quantity    = round(max(item.boq_quantity - new_cumulative, 0), 4)
    item.current_amount      = round(payload.current_quantity * item.rate, 2)
    item.cumulative_amount   = round(new_cumulative * item.rate, 2)
    db.commit()
    _recalc_bill(bill, db)
    db.refresh(item)
    return item


@router.post("/{bill_id}/submit", response_model=BillOut)
def submit_bill(bill_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    bill = db.query(RABill).filter(RABill.id == str(bill_id)).first()
    if not bill:
        raise HTTPException(404, "Not found")
    bill.status = BillStatus.SUBMITTED
    db.commit(); db.refresh(bill)
    return bill


@router.post("/{bill_id}/certify", response_model=BillOut)
def certify_bill(bill_id: UUID, certified_by: str = "", db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    bill = db.query(RABill).filter(RABill.id == str(bill_id)).first()
    if not bill:
        raise HTTPException(404, "Not found")
    bill.status = BillStatus.CERTIFIED
    if certified_by:
        bill.certified_by = certified_by
    db.commit(); db.refresh(bill)
    return bill


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    bill = db.query(RABill).filter(RABill.id == str(bill_id)).first()
    if not bill:
        raise HTTPException(404, "Not found")
    if bill.status in (BillStatus.CERTIFIED, BillStatus.PAID):
        raise HTTPException(403, "Cannot delete certified/paid bill")
    db.delete(bill); db.commit()
