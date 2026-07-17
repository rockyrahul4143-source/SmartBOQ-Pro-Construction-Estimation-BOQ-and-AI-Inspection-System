import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class WorkType(str, enum.Enum):
    EXCAVATION = "excavation"
    PCC = "pcc"
    RCC_FOOTING = "rcc_footing"
    RCC_COLUMN = "rcc_column"
    RCC_BEAM = "rcc_beam"
    RCC_SLAB = "rcc_slab"
    BRICKWORK = "brickwork"
    BLOCKWORK = "blockwork"
    PLASTER_EXTERNAL = "plaster_external"
    PLASTER_INTERNAL = "plaster_internal"
    FLOORING = "flooring"
    TILING = "tiling"
    PAINT_EXTERNAL = "paint_external"
    PAINT_INTERNAL = "paint_internal"
    STEEL_REINFORCEMENT = "steel_reinforcement"
    WATERPROOFING = "waterproofing"
    DOORS = "doors"
    WINDOWS = "windows"


class Estimate(Base):
    __tablename__ = "estimates"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True)
    work_type = Column(SAEnum(WorkType, native_enum=False), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String(30), nullable=False, default="m3")
    calculation_details = Column(Text, nullable=True)   # stored as JSON string for SQLite compat
    cement_bags = Column(Float, nullable=True, default=0.0)
    sand_cft = Column(Float, nullable=True, default=0.0)
    aggregate_cft = Column(Float, nullable=True, default=0.0)
    steel_kg = Column(Float, nullable=True, default=0.0)
    bricks_nos = Column(Float, nullable=True, default=0.0)
    blocks_nos = Column(Float, nullable=True, default=0.0)
    paint_ltr = Column(Float, nullable=True, default=0.0)
    tiles_sqm = Column(Float, nullable=True, default=0.0)
    material_cost = Column(Float, nullable=True, default=0.0)
    labour_cost = Column(Float, nullable=True, default=0.0)
    equipment_cost = Column(Float, nullable=True, default=0.0)
    total_cost = Column(Float, nullable=True, default=0.0)
    is_from_dxf = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="estimates")
