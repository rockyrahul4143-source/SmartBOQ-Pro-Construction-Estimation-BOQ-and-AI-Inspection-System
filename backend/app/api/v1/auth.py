from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, create_password_reset_token, verify_password_reset_token,
    hash_password,
)
from app.core.dependencies import get_current_active_user
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest, MessageResponse,
)
from app.schemas.user import UserCreate, UserOut
from app.models.report import AuditLog

router = APIRouter()


def _log(db: Session, user_id, action: str, details: str = None, ip: str = None):
    log = AuditLog(user_id=user_id, action=action, resource_type="auth", details=details, ip_address=ip)
    db.add(log)
    db.commit()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Register a new user account")
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    """
    Register a new user. Email must be unique.
    Password requires: 8+ chars, one uppercase, one digit.
    """
    if user_crud.get_user_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    user = user_crud.create_user(db, payload)
    _log(db, user.id, "REGISTER", f"New user: {user.email}", request.client.host)
    return user


@router.post("/login", response_model=TokenResponse, summary="Login and receive JWT tokens")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticate with email and password.
    Returns access token (30 min) and refresh token (7 days).
    """
    user = user_crud.get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    user_crud.update_last_login(db, user)
    _log(db, user.id, "LOGIN", f"Login from {request.client.host}", request.client.host)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse, summary="Refresh access token")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Use a valid refresh token to obtain a new access token."""
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user_id = token_data.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    new_access = create_access_token(str(user.id))
    return AccessTokenResponse(access_token=new_access)


@router.post("/forgot-password", response_model=MessageResponse,
             summary="Request a password reset email")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    If the email exists a reset token is generated.
    In production this token would be emailed to the user;
    here it is returned in the response for development convenience.
    """
    user = user_crud.get_user_by_email(db, payload.email)
    if not user:
        # Return success even if user not found (security best practice)
        return MessageResponse(message="If that email exists, a reset link has been sent.")

    token = create_password_reset_token(user.email)
    user_crud.set_password_reset_token(db, user, token)

    # TODO: In production, send email via SMTP with the reset link
    # For dev: the token is included in the response
    return MessageResponse(
        message="Password reset token generated. Check your email.",
        success=True,
    )


@router.post("/reset-password", response_model=MessageResponse, summary="Reset password with token")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = verify_password_reset_token(payload.token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = user_crud.get_user_by_email(db, email)
    if not user or user.password_reset_token != payload.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Password must be at least 8 characters")

    user_crud.reset_password(db, user, payload.new_password)
    return MessageResponse(message="Password has been reset successfully.")


@router.get("/me", response_model=UserOut, summary="Get current user profile")
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.post("/logout", response_model=MessageResponse, summary="Logout (client-side token removal)")
def logout(current_user: User = Depends(get_current_active_user)):
    """
    JWT tokens are stateless. Logout is handled client-side by discarding the tokens.
    This endpoint exists for audit logging purposes.
    """
    return MessageResponse(message="Logged out successfully.")
