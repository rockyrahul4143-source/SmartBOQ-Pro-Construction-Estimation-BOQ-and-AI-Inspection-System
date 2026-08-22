"""
Rate Analysis
=============
Breakdown of a BOQ item into:
  Material + Labour + Equipment + Wastage + Overhead + Profit = Final Rate
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class RateAnalysis(Base):
    __tablename__ = "rate_analyses"

    id          = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    sor_item_id = Column(GUID(), ForeignKey("sor_items.id", ondelete="CASCADE"), nullable=False)
    project_id  = Column(GUID(), ForeignKey("projects.id",  ondelete="SET NULL"), nullable=True)

    title       = Column(String(500), nullable=False)
    unit        = Column(String(30),  nullable=False)
    location    = Column(String(100), nullable=True)
    rate_year   = Column(String(10),  nullable=True)

    # Component totals (computed from children)
    material_total   = Column(Float, nullable=False, default=0.0)
    labour_total     = Column(Float, nullable=False, default=0.0)
    equipment_total  = Column(Float, nullable=False, default=0.0)
    direct_cost      = Column(Float, nullable=False, default=0.0)

    wastage_pct      = Column(Float, nullable=False, default=5.0)
    wastage_amount   = Column(Float, nullable=False, default=0.0)
    overhead_pct     = Column(Float, nullable=False, default=10.0)
    overhead_amount  = Column(Float, nullable=False, default=0.0)
    profit_pct       = Column(Float, nullable=False, default=10.0)
    profit_amount    = Column(Float, nullable=False, default=0.0)
    final_rate       = Column(Float, nullable=False, default=0.0)

    is_template      = Column(Boolean, default=False)  # reusable template
    notes            = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sor_item   = relationship("SORItem",         back_populates="rate_analyses")
    components = relationship("RateComponent",   back_populates="analysis",
                              cascade="all, delete-orphan")


class RateComponent(Base):
    """One line in a rate analysis (e.g. Cement @ ₹420 × 8.5 bags = ₹3,570)"""
    __tablename__ = "rate_components"

    id          = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    analysis_id = Column(GUID(), ForeignKey("rate_analyses.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(GUID(), ForeignKey("materials.id"), nullable=True)  # link to material if applicable

    component_type = Column(String(20), nullable=False)   # "material" | "labour" | "equipment"
    description    = Column(String(500), nullable=False)
    unit           = Column(String(30),  nullable=False)
    quantity       = Column(Float, nullable=False, default=0.0)
    rate           = Column(Float, nullable=False, default=0.0)
    amount         = Column(Float, nullable=False, default=0.0)   # = quantity × rate
    sort_order     = Column(Float, nullable=False, default=0.0)

    analysis = relationship("RateAnalysis", back_populates="components")
    material = relationship("Material")
