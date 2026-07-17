import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum as SAEnum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class ReportType(str, enum.Enum):
    PROJECT = "project"
    QUANTITY = "quantity"
    BOQ = "boq"
    COST = "cost"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"


class Report(Base):
    __tablename__ = "reports"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    generated_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    report_type = Column(SAEnum(ReportType, native_enum=False), nullable=False)
    report_format = Column(SAEnum(ReportFormat, native_enum=False), nullable=False, default=ReportFormat.PDF)
    title = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=True)
    file_size_kb = Column(String(20), nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="reports")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs")
