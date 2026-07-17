from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from uuid import UUID
from app.models.user import UserRole


# ── Base ─────────────────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.ESTIMATION_ENGINEER
    phone: Optional[str] = None
    company: Optional[str] = None
    designation: Optional[str] = None


# ── Create / Register ─────────────────────────────────
class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ── Update ─────────────────────────────────────────────
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    designation: Optional[str] = None
    profile_picture: Optional[str] = None


class UserUpdateRole(BaseModel):
    role: UserRole
    is_active: Optional[bool] = None


class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ── Response ──────────────────────────────────────────
class UserOut(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserOutBrief(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}
