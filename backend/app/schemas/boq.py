from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator
from uuid import UUID
from app.models.boq import BOQStatus


class BOQItemBase(BaseModel):
    item_no: str
    description: str
    specification: Optional[str] = None
    unit: str
    quantity: float
    rate: float = 0.0
    material_rate: Optional[float] = 0.0
    labour_rate: Optional[float] = 0.0
    equipment_rate: Optional[float] = 0.0
    is_heading: bool = False
    is_provisional: bool = False
    work_type: Optional[str] = None
    material_id: Optional[UUID] = None

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v):
        if v < 0:
            raise ValueError("Quantity cannot be negative")
        return v


class BOQItemCreate(BOQItemBase):
    pass


class BOQItemUpdate(BaseModel):
    description: Optional[str] = None
    specification: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    rate: Optional[float] = None
    material_rate: Optional[float] = None
    labour_rate: Optional[float] = None
    equipment_rate: Optional[float] = None
    is_provisional: Optional[bool] = None
    # NOTE: amount is NOT here — it is calculated server-side as quantity × rate


class BOQItemOut(BOQItemBase):
    id: UUID
    boq_id: UUID
    amount: float
    created_at: datetime
    model_config = {"from_attributes": True}


class BOQCreate(BaseModel):
    project_id: UUID
    title: str = "Bill of Quantities"
    overhead_pct: float = 10.0
    profit_pct: float = 10.0
    contingency_pct: float = 5.0
    currency: str = "INR"
    notes: Optional[str] = None


class BOQUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[BOQStatus] = None
    overhead_pct: Optional[float] = None
    profit_pct: Optional[float] = None
    contingency_pct: Optional[float] = None
    notes: Optional[str] = None


class BOQOut(BaseModel):
    id: UUID
    project_id: UUID
    boq_number: str
    revision: int
    title: str
    status: BOQStatus
    subtotal: Optional[float] = 0.0
    overhead_pct: float
    overhead_amount: Optional[float] = 0.0
    profit_pct: float
    profit_amount: Optional[float] = 0.0
    contingency_pct: float
    contingency_amount: Optional[float] = 0.0
    grand_total: Optional[float] = 0.0
    currency: str
    notes: Optional[str] = None
    items: List[BOQItemOut] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class BOQListItem(BaseModel):
    id: UUID
    project_id: UUID
    boq_number: str
    revision: int
    title: str
    status: BOQStatus
    grand_total: Optional[float] = 0.0
    currency: str
    created_at: datetime
    model_config = {"from_attributes": True}
