from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, field_validator
from uuid import UUID
from app.models.estimate import WorkType
import json


class EstimateOut(BaseModel):
    id: UUID
    project_id: UUID
    building_id: Optional[UUID] = None
    work_type: WorkType
    quantity: float
    unit: str
    # calculation_details stored as TEXT in SQLite — parse it to dict here
    calculation_details: Optional[Any] = None

    cement_bags: Optional[float] = 0.0
    sand_cft: Optional[float] = 0.0
    aggregate_cft: Optional[float] = 0.0
    steel_kg: Optional[float] = 0.0
    bricks_nos: Optional[float] = 0.0
    blocks_nos: Optional[float] = 0.0
    paint_ltr: Optional[float] = 0.0
    tiles_sqm: Optional[float] = 0.0

    material_cost: Optional[float] = 0.0
    labour_cost: Optional[float] = 0.0
    equipment_cost: Optional[float] = 0.0
    total_cost: Optional[float] = 0.0

    is_from_dxf: bool = False
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("calculation_details", mode="before")
    @classmethod
    def parse_details(cls, v: Any) -> Any:
        """SQLite stores JSON as TEXT — parse it back to dict."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

    @field_validator("work_type", mode="before")
    @classmethod
    def parse_work_type(cls, v: Any) -> WorkType:
        """Handle both string and enum values from SQLite."""
        if isinstance(v, WorkType):
            return v
        if isinstance(v, str):
            try:
                return WorkType(v)
            except ValueError:
                return v
        return v

    model_config = {"from_attributes": True}


class EstimateSummary(BaseModel):
    project_id: UUID
    building_id: Optional[UUID] = None
    total_cement_bags: float = 0.0
    total_sand_cft: float = 0.0
    total_aggregate_cft: float = 0.0
    total_steel_kg: float = 0.0
    total_steel_tons: float = 0.0
    total_bricks: float = 0.0
    total_blocks: float = 0.0
    total_paint_ltr: float = 0.0
    total_tiles_sqm: float = 0.0
    total_material_cost: float = 0.0
    total_labour_cost: float = 0.0
    total_equipment_cost: float = 0.0
    grand_total_cost: float = 0.0
    items: List[EstimateOut] = []


class FullEstimationResult(BaseModel):
    project_id: UUID
    building_id: UUID
    results: Dict[str, Any]
    summary: EstimateSummary
