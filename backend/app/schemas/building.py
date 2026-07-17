from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator
from uuid import UUID


# ── Room ──────────────────────────────────────────────
class RoomBase(BaseModel):
    floor_number: int = 0
    room_name: str
    length: float
    width: float
    height: Optional[float] = None

    @field_validator("length", "width")
    @classmethod
    def positive_dimension(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Dimension must be greater than zero")
        return v


class RoomCreate(RoomBase):
    pass


class RoomOut(RoomBase):
    id: UUID
    building_id: UUID
    area: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Building ──────────────────────────────────────────
class BuildingBase(BaseModel):
    building_name: str = "Main Building"
    num_floors: int = 1

    # Plot / Foundation
    plot_length: Optional[float] = None
    plot_width: Optional[float] = None
    excavation_depth: Optional[float] = 1.5

    # Footing
    footing_length: Optional[float] = 1.2
    footing_width: Optional[float] = 1.2
    footing_depth: Optional[float] = 0.3
    num_footings: Optional[int] = 0

    # PCC
    pcc_thickness: Optional[float] = 0.075

    # Columns
    column_length: Optional[float] = 0.3
    column_width: Optional[float] = 0.3
    floor_height: Optional[float] = 3.0
    num_columns: Optional[int] = 0

    # Beams
    beam_width: Optional[float] = 0.23
    beam_depth: Optional[float] = 0.45
    total_beam_length: Optional[float] = 0.0

    # Slab
    slab_length: Optional[float] = None
    slab_width: Optional[float] = None
    slab_thickness: Optional[float] = 0.125

    # Walls
    wall_thickness_external: Optional[float] = 0.23
    wall_thickness_internal: Optional[float] = 0.115
    total_external_wall_length: Optional[float] = 0.0
    total_internal_wall_length: Optional[float] = 0.0
    wall_height: Optional[float] = 3.0

    # Plaster
    plaster_thickness_external: Optional[float] = 0.020
    plaster_thickness_internal: Optional[float] = 0.012

    # Finishes
    flooring_type: Optional[str] = "tiles"
    tile_size: Optional[float] = 0.6
    tile_wastage_pct: Optional[float] = 10.0
    paint_coats: Optional[int] = 2

    # Openings
    num_doors: Optional[int] = 0
    door_width: Optional[float] = 0.9
    door_height: Optional[float] = 2.1
    num_windows: Optional[int] = 0
    window_width: Optional[float] = 1.2
    window_height: Optional[float] = 1.2

    # Steel
    steel_percentage_slab: Optional[float] = 1.0
    steel_percentage_column: Optional[float] = 2.5
    steel_percentage_beam: Optional[float] = 2.0

    # Waterproofing
    waterproofing_area: Optional[float] = 0.0

    notes: Optional[str] = None


class BuildingCreate(BuildingBase):
    project_id: UUID


class BuildingUpdate(BaseModel):
    building_name: Optional[str] = None
    num_floors: Optional[int] = None
    plot_length: Optional[float] = None
    plot_width: Optional[float] = None
    excavation_depth: Optional[float] = None
    footing_length: Optional[float] = None
    footing_width: Optional[float] = None
    footing_depth: Optional[float] = None
    num_footings: Optional[int] = None
    pcc_thickness: Optional[float] = None
    column_length: Optional[float] = None
    column_width: Optional[float] = None
    floor_height: Optional[float] = None
    num_columns: Optional[int] = None
    beam_width: Optional[float] = None
    beam_depth: Optional[float] = None
    total_beam_length: Optional[float] = None
    slab_length: Optional[float] = None
    slab_width: Optional[float] = None
    slab_thickness: Optional[float] = None
    wall_thickness_external: Optional[float] = None
    wall_thickness_internal: Optional[float] = None
    total_external_wall_length: Optional[float] = None
    total_internal_wall_length: Optional[float] = None
    wall_height: Optional[float] = None
    plaster_thickness_external: Optional[float] = None
    plaster_thickness_internal: Optional[float] = None
    flooring_type: Optional[str] = None
    tile_size: Optional[float] = None
    tile_wastage_pct: Optional[float] = None
    paint_coats: Optional[int] = None
    num_doors: Optional[int] = None
    door_width: Optional[float] = None
    door_height: Optional[float] = None
    num_windows: Optional[int] = None
    window_width: Optional[float] = None
    window_height: Optional[float] = None
    steel_percentage_slab: Optional[float] = None
    steel_percentage_column: Optional[float] = None
    steel_percentage_beam: Optional[float] = None
    waterproofing_area: Optional[float] = None
    notes: Optional[str] = None


class BuildingOut(BuildingBase):
    id: UUID
    project_id: UUID
    rooms: List[RoomOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
