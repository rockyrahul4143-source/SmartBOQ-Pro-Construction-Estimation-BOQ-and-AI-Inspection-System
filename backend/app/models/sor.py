"""
Schedule of Rates (SOR) / Item Master
======================================
Central item library reusable across:
  Measurement → BOQ → Rate Analysis → Billing → Reports
"""
import enum, uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class WorkCategory(str, enum.Enum):
    EARTHWORK        = "earthwork"
    PCC              = "pcc"
    RCC              = "rcc"
    REINFORCEMENT    = "reinforcement"
    FORMWORK         = "formwork"
    MASONRY          = "masonry"
    PLASTER          = "plaster"
    FLOORING         = "flooring"
    WATERPROOFING    = "waterproofing"
    PAINTING         = "painting"
    DOORS_WINDOWS    = "doors_windows"
    PLUMBING         = "plumbing"
    ELECTRICAL       = "electrical"
    ROAD             = "road"
    OTHER            = "other"


class RateSource(str, enum.Enum):
    CPWD_DSR   = "cpwd_dsr"
    STATE_PWD  = "state_pwd"
    MOR_TH     = "morth"
    PROJECT    = "project"
    CUSTOM     = "custom"


class SORItem(Base):
    """One row in the Schedule of Rates / Item Master."""
    __tablename__ = "sor_items"

    id          = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    item_code   = Column(String(50),  unique=True, nullable=False, index=True)
    description = Column(Text,         nullable=False)
    specification = Column(Text,       nullable=True)
    category    = Column(SAEnum(WorkCategory, native_enum=False), nullable=False, default=WorkCategory.OTHER)
    sub_category = Column(String(100), nullable=True)
    unit        = Column(String(30),   nullable=False)

    # Rates
    basic_rate  = Column(Float, nullable=False, default=0.0)   # material + labour + equipment
    material_rate = Column(Float, nullable=True, default=0.0)
    labour_rate   = Column(Float, nullable=True, default=0.0)
    equipment_rate= Column(Float, nullable=True, default=0.0)
    rate_source   = Column(SAEnum(RateSource, native_enum=False), nullable=False, default=RateSource.CUSTOM)
    rate_year     = Column(Integer, nullable=True)
    rate_location = Column(String(100), nullable=True)         # state / district

    # Calculation helpers
    formula_type  = Column(String(50), nullable=True)          # "volume", "area", "length", "number"
    formula_note  = Column(Text, nullable=True)                # human-readable formula hint
    mix_design    = Column(String(30), nullable=True)          # M20 / M25 / 1:4:8 etc.

    # Meta
    is_active     = Column(Boolean, default=True, nullable=False)
    is_system     = Column(Boolean, default=False, nullable=False)  # built-in, cannot delete
    tags          = Column(String(500), nullable=True)          # comma-separated search tags
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rate_analyses     = relationship("RateAnalysis",    back_populates="sor_item", cascade="all, delete-orphan")
    measurement_items = relationship("MeasurementItem", back_populates="sor_item")
