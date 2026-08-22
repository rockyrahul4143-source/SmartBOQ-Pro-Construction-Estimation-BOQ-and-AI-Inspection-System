"""
Running Account (RA) Billing
=============================
Running bills raised against a BOQ.
Each RABill has items corresponding to BOQ items,
recording previous/current/cumulative quantities.
"""
import enum, uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class BillStatus(str, enum.Enum):
    DRAFT     = "draft"
    SUBMITTED = "submitted"
    CERTIFIED = "certified"
    PAID      = "paid"


class RABill(Base):
    __tablename__ = "ra_bills"

    id         = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    boq_id     = Column(GUID(), ForeignKey("boqs.id",     ondelete="CASCADE"), nullable=False)

    bill_number      = Column(String(50),  nullable=False)
    bill_date        = Column(DateTime,    nullable=True)
    period_from      = Column(DateTime,    nullable=True)
    period_to        = Column(DateTime,    nullable=True)
    status           = Column(String(20),  nullable=False, default=BillStatus.DRAFT)

    contractor_name  = Column(String(255), nullable=True)
    prepared_by      = Column(GUID(), ForeignKey("users.id"), nullable=True)
    certified_by     = Column(String(255), nullable=True)

    # Totals (computed)
    current_amount   = Column(Float, nullable=False, default=0.0)
    cumulative_amount= Column(Float, nullable=False, default=0.0)
    previous_amount  = Column(Float, nullable=False, default=0.0)
    deductions       = Column(Float, nullable=False, default=0.0)
    net_payable      = Column(Float, nullable=False, default=0.0)

    allow_excess     = Column(Boolean, default=False)  # allow qty > BOQ qty
    notes            = Column(Text,  nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project  = relationship("Project", foreign_keys=[project_id])
    boq      = relationship("BOQ",     foreign_keys=[boq_id])
    items    = relationship("RABillItem", back_populates="bill",
                            cascade="all, delete-orphan",
                            order_by="RABillItem.item_no")


class RABillItem(Base):
    """
    One item in an RA bill.
    Tracks: BOQ qty → previous → current → cumulative → balance
    """
    __tablename__ = "ra_bill_items"

    id          = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    bill_id     = Column(GUID(), ForeignKey("ra_bills.id",   ondelete="CASCADE"), nullable=False)
    boq_item_id = Column(GUID(), ForeignKey("boq_items.id"), nullable=True)

    item_no      = Column(String(20),  nullable=False)
    description  = Column(Text,        nullable=False)
    unit         = Column(String(30),  nullable=False)
    rate         = Column(Float,       nullable=False, default=0.0)

    # Quantities
    boq_quantity        = Column(Float, nullable=False, default=0.0)
    previous_quantity   = Column(Float, nullable=False, default=0.0)
    current_quantity    = Column(Float, nullable=False, default=0.0)
    cumulative_quantity = Column(Float, nullable=False, default=0.0)  # prev + current
    balance_quantity    = Column(Float, nullable=False, default=0.0)  # boq - cumulative

    # Amounts
    current_amount      = Column(Float, nullable=False, default=0.0)  # current_qty × rate
    cumulative_amount   = Column(Float, nullable=False, default=0.0)
    previous_amount     = Column(Float, nullable=False, default=0.0)

    is_heading   = Column(Boolean, default=False)
    remarks      = Column(String(500), nullable=True)

    bill     = relationship("RABill",    back_populates="items")
    boq_item = relationship("BOQItem",  foreign_keys=[boq_item_id])
