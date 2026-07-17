import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ESTIMATION_ENGINEER = "estimation_engineer"
    QUANTITY_SURVEYOR = "quantity_surveyor"
    PROJECT_MANAGER = "project_manager"


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole, native_enum=False), nullable=False, default=UserRole.ESTIMATION_ENGINEER)
    phone = Column(String(30), nullable=True)
    company = Column(String(255), nullable=True)
    designation = Column(String(255), nullable=True)
    profile_picture = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    projects = relationship("Project", back_populates="created_by_user", foreign_keys="Project.created_by")
    audit_logs = relationship("AuditLog", back_populates="user")
