from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    """Build SQLAlchemy engine. Called once at startup."""
    db_url = settings.DATABASE_URL

    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

    # PostgreSQL — patch URL if needed
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    if "neon.tech" in db_url and "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"

    # Update the in-memory settings so alembic also sees the fixed URL
    settings.DATABASE_URL = db_url

    return create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=2,       # Neon free: max 10 connections, keep footprint small
        max_overflow=3,    # max 5 total connections (was 15 — too many)
        pool_recycle=300,
        pool_timeout=30,
        connect_args={"connect_timeout": 10},
    )


engine       = _build_engine()
is_sqlite    = settings.DATABASE_URL.startswith("sqlite")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Enable foreign keys for SQLite
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
