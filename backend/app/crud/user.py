from typing import Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserUpdateRole
from app.core.security import hash_password, verify_password


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == str(user_id)).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def count_users(db: Session) -> int:
    return db.query(User).count()


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        phone=payload.phone,
        company=payload.company,
        designation=payload.designation,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, payload: UserUpdate) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def update_user_role(db: Session, user: User, payload: UserUpdateRole) -> User:
    user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
    if not verify_password(current_password, user.hashed_password):
        return False
    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


def set_password_reset_token(db: Session, user: User, token: str) -> None:
    from datetime import datetime, timedelta
    user.password_reset_token = token
    user.password_reset_expires = datetime.utcnow() + timedelta(hours=24)
    db.commit()


def reset_password(db: Session, user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()


def mark_verified(db: Session, user: User) -> None:
    user.is_verified = True
    db.commit()


def update_last_login(db: Session, user: User) -> None:
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()
