import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class MaterialCategory(str, enum.Enum):
    CEMENT = "cement"
    AGGREGATE = "aggregate"
    SAND = "sand"
    STEEL = "steel"
    BRICK = "brick"
    BLOCK = "block"
    PAINT = "paint"
    TILE = "tile"
    WATERPROOFING = "waterproofing"
    WOOD = "wood"
    GLASS = "glass"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    OTHER = "other"


class MaterialUnit(str, enum.Enum):
    KG = "kg"
    TON = "ton"
    BAG = "bag"
    CUBIC_METER = "m3"
    SQUARE_METER = "m2"
    LINEAR_METER = "lm"
    NUMBER = "no"
    LITER = "ltr"
    GALLON = "gal"


class Material(Base):
    __tablename__ = "materials"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    material_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(SAEnum(MaterialCategory, native_enum=False), nullable=False)
    unit = Column(SAEnum(MaterialUnit, native_enum=False), nullable=False)
    current_rate = Column(Float, nullable=False)
    rate_per_kg = Column(Float, nullable=True)
    supplier_name = Column(String(255), nullable=True)
    supplier_contact = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rate_history = relationship("MaterialRateHistory", back_populates="material", cascade="all, delete-orphan")
    boq_items = relationship("BOQItem", back_populates="material")


class MaterialRateHistory(Base):
    __tablename__ = "material_rate_history"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    material_id = Column(GUID(), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    old_rate = Column(Float, nullable=False)
    new_rate = Column(Float, nullable=False)
    changed_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(String(500), nullable=True)

    material = relationship("Material", back_populates="rate_history")
