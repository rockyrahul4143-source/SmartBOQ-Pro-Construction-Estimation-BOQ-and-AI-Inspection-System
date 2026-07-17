import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class BOQStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    APPROVED = "approved"
    REVISED = "revised"


class BOQ(Base):
    __tablename__ = "boqs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    boq_number = Column(String(50), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    title = Column(String(500), nullable=False, default="Bill of Quantities")
    status = Column(SAEnum(BOQStatus, native_enum=False), nullable=False, default=BOQStatus.DRAFT)
    prepared_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    approved_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    approval_date = Column(DateTime, nullable=True)
    subtotal = Column(Float, nullable=True, default=0.0)
    overhead_pct = Column(Float, nullable=True, default=10.0)
    overhead_amount = Column(Float, nullable=True, default=0.0)
    profit_pct = Column(Float, nullable=True, default=10.0)
    profit_amount = Column(Float, nullable=True, default=0.0)
    contingency_pct = Column(Float, nullable=True, default=5.0)
    contingency_amount = Column(Float, nullable=True, default=0.0)
    grand_total = Column(Float, nullable=True, default=0.0)
    currency = Column(String(10), nullable=False, default="INR")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="boqs")
    items = relationship("BOQItem", back_populates="boq", cascade="all, delete-orphan", order_by="BOQItem.item_no")


class BOQItem(Base):
    __tablename__ = "boq_items"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    boq_id = Column(GUID(), ForeignKey("boqs.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(GUID(), ForeignKey("materials.id"), nullable=True)
    item_no = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    specification = Column(Text, nullable=True)
    unit = Column(String(30), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    rate = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    material_rate = Column(Float, nullable=True, default=0.0)
    labour_rate = Column(Float, nullable=True, default=0.0)
    equipment_rate = Column(Float, nullable=True, default=0.0)
    is_heading = Column(Boolean, default=False, nullable=False)
    is_provisional = Column(Boolean, default=False, nullable=False)
    work_type = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    boq = relationship("BOQ", back_populates="items")
    material = relationship("Material", back_populates="boq_items")
