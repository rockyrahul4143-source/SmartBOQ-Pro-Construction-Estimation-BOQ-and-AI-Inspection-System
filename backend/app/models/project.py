import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum, Text, ForeignKey, Float, Integer, Date
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class BuildingType(str, enum.Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    INSTITUTIONAL = "institutional"
    MIXED_USE = "mixed_use"


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_code = Column(String(50), unique=True, nullable=False, index=True)
    project_name = Column(String(500), nullable=False)
    client_name = Column(String(255), nullable=False)
    client_contact = Column(String(100), nullable=True)
    client_email = Column(String(255), nullable=True)
    location = Column(String(500), nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True, default="Pakistan")
    building_type = Column(SAEnum(BuildingType, native_enum=False), nullable=False, default=BuildingType.RESIDENTIAL)
    num_floors = Column(Integer, nullable=False, default=1)
    total_built_up_area = Column(Float, nullable=True)
    plot_area = Column(Float, nullable=True)
    start_date = Column(Date, nullable=True)
    expected_completion = Column(Date, nullable=True)
    status = Column(SAEnum(ProjectStatus, native_enum=False), nullable=False, default=ProjectStatus.DRAFT)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    total_estimated_cost = Column(Float, nullable=True, default=0.0)
    currency = Column(String(10), nullable=False, default="INR")
    created_by = Column(GUID(), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    created_by_user = relationship("User", back_populates="projects", foreign_keys=[created_by])
    buildings = relationship("Building", back_populates="project", cascade="all, delete-orphan")
    boqs = relationship("BOQ", back_populates="project", cascade="all, delete-orphan")
    estimates = relationship("Estimate", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")
