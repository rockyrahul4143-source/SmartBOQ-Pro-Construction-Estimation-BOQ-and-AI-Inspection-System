from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Union


class Settings(BaseSettings):
    APP_NAME: str = "SmartBOQ Pro"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security — must be overridden in production via environment variable
    # The fallback value is only safe for local development
    SECRET_KEY: str = "local-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite:///./smartboq.db"

    # CORS — set ALLOWED_ORIGINS env var on Render to your exact Vercel URL
    # Example: ALLOWED_ORIGINS=https://smart-boq-pro-construction-estimati.vercel.app
    # Multiple origins: comma-separated
    # Local dev fallback — never use "*" in production
    ALLOWED_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:5174"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if v == "*":
            return ["*"]
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: str = "noreply@smartboq.com"
    EMAILS_FROM_NAME: str = "SmartBOQ Pro"

    # File Uploads
    UPLOAD_DIR: str = "/tmp/uploads"
    MAX_FILE_SIZE_MB: int = 50

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
