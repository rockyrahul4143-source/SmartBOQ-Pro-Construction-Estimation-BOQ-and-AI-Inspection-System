"""
BBS (Bar Bending Schedule) Models
==================================
BBSSheet  — one BBS sheet per member / project
BBSBar    — individual bar row in the sheet
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class BBSSheet(Base):
    __tablename__ = "bbs_sheets"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    sheet_number = Column(String(50),  nullable=False)          # BBS-001
    title        = Column(String(500), nullable=False)          # "Beam BBS — GF"
    member_type  = Column(String(30),  nullable=False, default="beam")  # beam|column|slab|footing

    # Source of information
    mode         = Column(String(20),  nullable=False, default="manual") # manual|auto|mixed

    # Drawing reference
    drawing_ref  = Column(String(200), nullable=True)
    drawing_file = Column(String(500), nullable=True)   # uploaded file path

    # Design parameters (used by engine if not overridden per-bar)
    fck          = Column(Integer,  nullable=False, default=20)
    fy           = Column(Integer,  nullable=False, default=500)
    clear_cover  = Column(Float,    nullable=True)
    bond_type    = Column(String(20), nullable=False, default="deformed")

    # Status
    is_approved  = Column(Boolean,  nullable=False, default=False)
    prepared_by  = Column(String(36), ForeignKey("users.id"), nullable=True)
    checked_by   = Column(String(255), nullable=True)
    notes        = Column(Text,     nullable=True)

    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bars = relationship(
        "BBSBar",
        back_populates="sheet",
        cascade="all, delete-orphan",
        order_by="BBSBar.sort_order",
    )


class BBSBar(Base):
    __tablename__ = "bbs_bars"

    id       = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    sheet_id = Column(String(36), ForeignKey("bbs_sheets.id", ondelete="CASCADE"), nullable=False)

    sort_order = Column(Integer, nullable=False, default=0)
    is_heading = Column(Boolean, nullable=False, default=False)

    # Bar identification
    bar_mark    = Column(String(50),  nullable=True)    # T1, B1, ST1, etc.
    position    = Column(String(100), nullable=True)    # "Top layer", "Bottom layer"
    member_mark = Column(String(100), nullable=True)    # EB5, C1, etc.
    floor_level = Column(String(50),  nullable=True)

    # Bar geometry
    dia_mm      = Column(Integer, nullable=True)
    bar_shape   = Column(String(50), nullable=False, default="straight")
    num_bars    = Column(Integer, nullable=True, default=0)

    # Input dimensions (mm)
    clear_span_mm      = Column(Float, nullable=True)
    support_near_mm    = Column(Float, nullable=True)
    support_far_mm     = Column(Float, nullable=True)
    section_b_mm       = Column(Float, nullable=True)   # breadth
    section_d_mm       = Column(Float, nullable=True)   # depth
    cover_mm           = Column(Float, nullable=True)
    spacing_mm         = Column(Float, nullable=True)   # stirrups
    storey_height_mm   = Column(Float, nullable=True)   # columns
    zone_length_mm     = Column(Float, nullable=True)   # stirrup zone

    # Hook / lap / development
    has_hook_near      = Column(Boolean, nullable=False, default=False)
    has_hook_far       = Column(Boolean, nullable=False, default=False)
    hook_type          = Column(String(20), nullable=False, default="standard")
    lap_mm             = Column(Float, nullable=True)
    dev_length_mm      = Column(Float, nullable=True)

    # Calculated results (stored after engine runs)
    cutting_length_mm  = Column(Float, nullable=True)
    total_length_mm    = Column(Float, nullable=True)
    unit_weight_kg_per_m = Column(Float, nullable=True)
    total_weight_kg    = Column(Float, nullable=True)

    # Audit
    formula            = Column(Text,    nullable=True)  # human-readable formula used
    source             = Column(String(50), nullable=False, default="manual")
    # manual|drawing_schedule|dxf_geometry|drawing_section|general_note|calculated
    status             = Column(String(50), nullable=False, default="calculated")
    # calculated|verify_required|conflict|missing_input
    remarks            = Column(Text,    nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sheet = relationship("BBSSheet", back_populates="bars")
