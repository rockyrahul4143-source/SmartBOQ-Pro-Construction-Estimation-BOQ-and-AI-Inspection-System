from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator
from uuid import UUID

from app.models.project import BuildingType, ProjectStatus


# ── Shared base ───────────────────────────────────────
class ProjectBase(BaseModel):
    project_name: str
    client_name: Optional[str] = None   # optional — not required for quick projects
    client_contact: Optional[str] = None
    client_email: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    building_type: BuildingType = BuildingType.RESIDENTIAL
    num_floors: int = 1
    total_built_up_area: Optional[float] = None
    plot_area: Optional[float] = None
    start_date: Optional[date] = None
    expected_completion: Optional[date] = None
    status: ProjectStatus = ProjectStatus.DRAFT
    description: Optional[str] = None
    notes: Optional[str] = None
    currency: str = "INR"

    @field_validator("num_floors")
    @classmethod
    def validate_floors(cls, v: int) -> int:
        if v < 1 or v > 200:
            raise ValueError("Number of floors must be between 1 and 200")
        return v


# ── Create ────────────────────────────────────────────
class ProjectCreate(ProjectBase):
    pass


# ── Update ────────────────────────────────────────────
class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    client_email: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    building_type: Optional[BuildingType] = None
    num_floors: Optional[int] = None
    total_built_up_area: Optional[float] = None
    plot_area: Optional[float] = None
    start_date: Optional[date] = None
    expected_completion: Optional[date] = None
    status: Optional[ProjectStatus] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    total_estimated_cost: Optional[float] = None


# ── Response ──────────────────────────────────────────
class ProjectOut(ProjectBase):
    id: UUID
    project_code: str
    total_estimated_cost: Optional[float] = 0.0
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    id: UUID
    project_code: str
    project_name: str
    client_name: Optional[str] = None
    location: Optional[str] = None
    building_type: BuildingType
    num_floors: int
    status: ProjectStatus
    total_estimated_cost: Optional[float] = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStats(BaseModel):
    total_projects: int
    draft: int
    active: int
    on_hold: int
    completed: int
    archived: int
    total_estimated_cost: float
