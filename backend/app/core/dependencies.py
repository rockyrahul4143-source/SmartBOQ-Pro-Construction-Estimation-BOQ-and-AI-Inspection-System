from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def _get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def get_current_user(
    payload: dict = Depends(_get_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


# ── Role Guards ───────────────────────────────────────
class RoleChecker:
    """Dependency factory that raises 403 if the user doesn't have an allowed role."""

    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {[r.value for r in self.allowed_roles]}",
            )
        return current_user


# Convenience role dependencies
require_admin = RoleChecker([UserRole.ADMIN])
require_admin_or_pm = RoleChecker([UserRole.ADMIN, UserRole.PROJECT_MANAGER])
require_estimator = RoleChecker([
    UserRole.ADMIN,
    UserRole.ESTIMATION_ENGINEER,
    UserRole.QUANTITY_SURVEYOR,
    UserRole.PROJECT_MANAGER,
])
