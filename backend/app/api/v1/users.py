from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate, UserUpdateRole, ChangePassword, UserOutBrief
from app.schemas.auth import MessageResponse

router = APIRouter()


# ── Profile ───────────────────────────────────────────
@router.get("/me", response_model=UserOut, summary="Get own profile")
def get_my_profile(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put("/me", response_model=UserOut, summary="Update own profile")
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return user_crud.update_user(db, current_user, payload)


@router.post("/me/change-password", response_model=MessageResponse, summary="Change own password")
def change_my_password(
    payload: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    success = user_crud.change_password(db, current_user, payload.current_password, payload.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    return MessageResponse(message="Password changed successfully.")


# ── Admin: List & Manage Users ────────────────────────
@router.get("/", response_model=List[UserOut], summary="List all users (Admin only)")
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return user_crud.get_all_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserOut, summary="Get user by ID (Admin only)")
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}/role", response_model=UserOut, summary="Update user role/status (Admin only)")
def update_user_role(
    user_id: UUID,
    payload: UserUpdateRole,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify your own role")
    return user_crud.update_user_role(db, user, payload)


@router.delete("/{user_id}", response_model=MessageResponse, summary="Delete user (Admin only)")
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    user_crud.delete_user(db, user)
    return MessageResponse(message=f"User {user.email} deleted successfully.")


@router.get("/brief/all", response_model=List[UserOutBrief], summary="List users (brief) for dropdowns")
def list_users_brief(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return user_crud.get_all_users(db, limit=500)
