"""Project File Store — stores uploaded drawings/schedules per project."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from app.db.base import Base


class ProjectFile(Base):
    __tablename__ = "project_files"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    filename      = Column(String(500),  nullable=False)
    original_name = Column(String(500),  nullable=False)
    file_type     = Column(String(30),   nullable=False)   # dxf|pdf|dwg|image|other
    file_category = Column(String(50),   nullable=True)    # beam_schedule|column_schedule|etc
    file_path     = Column(String(1000), nullable=True)
    file_size_kb  = Column(Float,        nullable=True)

    extraction_status = Column(String(20), nullable=False, default="pending")
    extracted_data    = Column(Text,       nullable=True)  # JSON
    member_count      = Column(Integer,    nullable=True,  default=0)
    member_list       = Column(Text,       nullable=True)  # comma-separated
    extraction_notes  = Column(Text,       nullable=True)

    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime,  default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime,  default=datetime.utcnow, onupdate=datetime.utcnow)
