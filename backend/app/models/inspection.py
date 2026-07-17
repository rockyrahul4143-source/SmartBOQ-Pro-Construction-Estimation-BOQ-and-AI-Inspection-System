import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class InspectionType(str, enum.Enum):
    CONCRETE_CRACK  = "concrete_crack"
    SURFACE_CRACK   = "surface_crack"
    ROAD_DAMAGE     = "road_damage"
    BUILDING_SAFETY = "building_safety"


class SeverityLevel(str, enum.Enum):
    NONE     = "none"
    LOW      = "low"
    MODERATE = "moderate"
    HIGH     = "high"
    CRITICAL = "critical"


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    inspected_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    inspection_type = Column(SAEnum(InspectionType, native_enum=False), nullable=False)
    image_path = Column(String(1000), nullable=True)
    image_filename = Column(String(500), nullable=True)
    model_name = Column(String(100), nullable=True)
    predicted_class = Column(String(200), nullable=True)
    confidence = Column(Float, nullable=True)
    severity = Column(SAEnum(SeverityLevel, native_enum=False), nullable=False, default=SeverityLevel.NONE)
    severity_score = Column(Float, nullable=True)
    detection_boxes = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    repair_urgency = Column(String(50), nullable=True)
    estimated_repair_cost_min = Column(Float, nullable=True)
    estimated_repair_cost_max = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project      = relationship("Project", foreign_keys=[project_id])
    inspector    = relationship("User", foreign_keys=[inspected_by])
