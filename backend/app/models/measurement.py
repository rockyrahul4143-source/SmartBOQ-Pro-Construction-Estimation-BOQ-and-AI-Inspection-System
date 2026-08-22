"""
Measurement Book
================
Engineers record actual site measurements here.
Each MeasurementBook → many MeasurementItems (rows).
Each item stores dimensions + shows formula + calculates quantity.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class MeasurementBook(Base):
    __tablename__ = "measurement_books"

    id           = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id   = Column(GUID(), ForeignKey("projects.id",  ondelete="CASCADE"), nullable=False)
    building_id  = Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True)
    boq_id       = Column(GUID(), ForeignKey("boqs.id",      ondelete="SET NULL"), nullable=True)

    mb_number    = Column(String(50),  nullable=False)
    title        = Column(String(500), nullable=False, default="Measurement Book")
    description  = Column(Text,        nullable=True)
    prepared_by  = Column(GUID(), ForeignKey("users.id"), nullable=True)
    checked_by   = Column(String(255), nullable=True)
    date_of_measurement = Column(DateTime, nullable=True)

    is_approved  = Column(Boolean, default=False)
    notes        = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project   = relationship("Project",  foreign_keys=[project_id])
    building  = relationship("Building", foreign_keys=[building_id])
    items     = relationship("MeasurementItem", back_populates="book",
                             cascade="all, delete-orphan", order_by="MeasurementItem.sort_order")


class MeasurementItem(Base):
    """
    One line in the measurement book.
    Supports: Length × Width × Height/Depth × Nos = Quantity
    Formula is stored so engineers can verify.
    """
    __tablename__ = "measurement_items"

    id          = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    book_id     = Column(GUID(), ForeignKey("measurement_books.id", ondelete="CASCADE"), nullable=False)
    sor_item_id = Column(GUID(), ForeignKey("sor_items.id"),         nullable=True)

    # Display
    sort_order  = Column(Integer, nullable=False, default=0)
    is_heading  = Column(Boolean, default=False)          # section heading row
    item_ref    = Column(String(50),  nullable=True)      # A.1, A.2 etc.
    description = Column(Text,        nullable=False)
    unit        = Column(String(30),  nullable=True)

    # Dimensions (all optional — fill what applies)
    length      = Column(Float, nullable=True)
    width       = Column(Float, nullable=True)
    height      = Column(Float, nullable=True)   # or depth or thickness
    nos         = Column(Float, nullable=True, default=1.0)

    # Calculated
    quantity         = Column(Float, nullable=True, default=0.0)
    formula_display  = Column(Text,  nullable=True)   # e.g. "1.50 × 1.50 × 0.30 × 12 = 8.10 m³"
    is_manual_override = Column(Boolean, default=False)
    override_reason    = Column(String(500), nullable=True)

    # Deductions
    is_deduction = Column(Boolean, default=False)   # negative quantity (deduct opening etc.)
    deduction_ref = Column(String(100), nullable=True)

    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book     = relationship("MeasurementBook",  back_populates="items")
    sor_item = relationship("SORItem", back_populates="measurement_items")
