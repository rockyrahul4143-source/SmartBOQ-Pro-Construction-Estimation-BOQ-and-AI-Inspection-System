from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# ── Build engine kwargs ───────────────────────────────
if is_sqlite:
    engine_kwargs = {
        "connect_args": {"check_same_thread": False},
    }
else:
    # PostgreSQL (Render, Neon, Supabase, etc.)
    # Neon requires SSL — add sslmode=require if not already present
    db_url = settings.DATABASE_URL
    if "neon.tech" in db_url and "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    # Override settings URL so engine uses the SSL-patched URL
    settings.DATABASE_URL = db_url

    engine_kwargs = {
        "pool_pre_ping":  True,    # verify connection before use
        "pool_size":      5,       # Neon free tier: max 10 connections
        "max_overflow":   10,
        "pool_recycle":   300,     # recycle connections every 5 min
        "connect_args":   {"connect_timeout": 10},
    }

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    **engine_kwargs,
)

# Enable foreign keys for SQLite
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
