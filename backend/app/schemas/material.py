from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator
from uuid import UUID
from app.models.material import MaterialCategory, MaterialUnit


class MaterialBase(BaseModel):
    name: str
    category: MaterialCategory
    unit: MaterialUnit
    current_rate: float
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    description: Optional[str] = None

    @field_validator("current_rate")
    @classmethod
    def positive_rate(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Rate cannot be negative")
        return v


class MaterialCreate(MaterialBase):
    material_code: Optional[str] = None


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[MaterialCategory] = None
    unit: Optional[MaterialUnit] = None
    current_rate: Optional[float] = None
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class MaterialRateUpdate(BaseModel):
    new_rate: float
    notes: Optional[str] = None

    @field_validator("new_rate")
    @classmethod
    def positive_rate(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Rate must be positive")
        return v


class RateHistoryOut(BaseModel):
    id: UUID
    material_id: UUID
    old_rate: float
    new_rate: float
    changed_at: datetime
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class MaterialOut(MaterialBase):
    id: UUID
    material_code: str
    rate_per_kg: Optional[float] = None
    is_active: bool
    last_updated: datetime
    created_at: datetime
    model_config = {"from_attributes": True}


class MaterialListItem(BaseModel):
    id: UUID
    material_code: str
    name: str
    category: MaterialCategory
    unit: MaterialUnit
    current_rate: float
    supplier_name: Optional[str] = None
    is_active: bool
    last_updated: datetime
    model_config = {"from_attributes": True}


class RateAnalysisInput(BaseModel):
    work_description: str
    unit: str
    material_name: str
    material_quantity: float
    material_rate: float
    labour_description: str = "Skilled + Unskilled Labour"
    labour_quantity: float = 1.0
    labour_rate: float = 1500.0
    helper_quantity: float = 0.5
    helper_rate: float = 800.0
    equipment_description: Optional[str] = None
    equipment_rate: float = 0.0
    overhead_pct: float = 10.0
    profit_pct: float = 10.0
    contingency_pct: float = 5.0


class RateAnalysisResult(BaseModel):
    work_description: str
    unit: str
    material_cost: float
    labour_cost: float
    equipment_cost: float
    direct_cost: float
    overhead_amount: float
    profit_amount: float
    contingency_amount: float
    total_rate: float
    breakdown: dict


class CostEstimateInput(BaseModel):
    project_id: UUID
    overhead_pct: float = 10.0
    profit_pct: float = 10.0
    contingency_pct: float = 5.0
    labour_pct_of_material: float = 35.0
    equipment_pct_of_material: float = 10.0


class CostBreakdown(BaseModel):
    project_id: UUID
    material_cost: float
    labour_cost: float
    equipment_cost: float
    direct_cost: float
    overhead_pct: float
    overhead_amount: float
    profit_pct: float
    profit_amount: float
    contingency_pct: float
    contingency_amount: float
    grand_total: float
    cost_by_work_type: List[dict] = []
