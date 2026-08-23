"""Reset password for rockyrahul4143@gmail.com to Rocky@1234"""
import sys, os
os.environ["DATABASE_URL"] = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]   = "local-dev-secret-key-smartboq-pro-2024"

from app.db.base import SessionLocal
from app.models.user import User
from app.core.security import hash_password

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == "rockyrahul4143@gmail.com").first()
    if user:
        user.hashed_password = hash_password("Rocky@1234")
        db.commit()
        print(f"Password reset for {user.email}")
        print("New password: Rocky@1234")
    else:
        print("User not found")
finally:
    db.close()
