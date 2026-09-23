"""
SmartBOQ Pro — Render.com Production Startup
=============================================
Supports: Render PostgreSQL, Neon PostgreSQL, Supabase PostgreSQL

Strategy:
  1. Fix DATABASE_URL (postgres:// → postgresql://, add SSL for Neon)
  2. SQLAlchemy create_all() — safe, idempotent, never drops data
  3. Seed permanent users + materials (skips if already exist)
  4. Start uvicorn
"""
import os, sys, subprocess, pathlib

# ── Environment defaults ─────────────────────────────
os.environ.setdefault("APP_ENV",    "production")
os.environ.setdefault("DEBUG",      "false")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

os.makedirs("/tmp/uploads",             exist_ok=True)
os.makedirs("/tmp/uploads/inspections", exist_ok=True)

print("=" * 55)
print("  SmartBOQ Pro — Production Startup")
print("=" * 55)

db_url = os.getenv("DATABASE_URL", "")
secret  = os.getenv("SECRET_KEY", "")

print(f"  DATABASE_URL : {'SET ✓' if db_url else 'MISSING ✗'}")
print(f"  SECRET_KEY   : {'SET ✓' if secret  else 'MISSING ✗'}")

if not db_url:
    print("\n  FATAL: DATABASE_URL not set. Add it in Render → Environment.\n")
    sys.exit(1)

# ── Fix URL scheme ────────────────────────────────────
# Heroku/Render/Neon may give postgres:// — SQLAlchemy needs postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    print("  Fixed: postgres:// → postgresql://")

# ── Neon SSL ──────────────────────────────────────────
# Neon PostgreSQL requires SSL — add sslmode=require if not present
if "neon.tech" in db_url and "sslmode" not in db_url:
    sep = "&" if "?" in db_url else "?"
    db_url = db_url + sep + "sslmode=require"
    print("  Added: sslmode=require (Neon PostgreSQL)")

os.environ["DATABASE_URL"] = db_url
db_provider = "Neon" if "neon.tech" in db_url else "PostgreSQL"
print(f"  Provider: {db_provider}")

# ── Add backend to sys.path ───────────────────────────
BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))

# ── Step 1: Create all tables ─────────────────────────
print("\n  [1/3] Creating/verifying tables...")
try:
    from app.db.base import Base, engine
    import app.models  # noqa — register all ORM models
    Base.metadata.create_all(bind=engine)
    print("        Tables OK ✓")
except Exception as e:
    print(f"        ERROR: {e}")
    print("        Check DATABASE_URL and network connectivity.")
    sys.exit(1)

# ── Step 2: Alembic migration stamp ──────────────────
# stamp head then upgrade — safe even if already at head
print("  [2/3] Running migrations...")
try:
    subprocess.run(
        ["alembic", "stamp", "head"],
        capture_output=True, text=True, cwd=str(BASE)
    )
    r2 = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=str(BASE)
    )
    if r2.returncode == 0:
        print("        Migrations OK ✓")
    else:
        print(f"        Note: {r2.stderr[-200:] if r2.stderr else 'none'}")
        print("        (tables already created via create_all — continuing)")
except FileNotFoundError:
    print("        alembic not found — skipping (tables via create_all)")
except Exception as e:
    print(f"        Migration skipped: {e}")

# ── Step 3: Seed data ─────────────────────────────────
print("  [3/3] Seeding permanent data...")
try:
    from app.scripts.seed_data import run as seed_run
    seed_run()
    print("        Seed OK ✓")
except Exception as e:
    print(f"        Seed note: {e}")

# ── Start server ──────────────────────────────────────
port = int(os.getenv("PORT", 8000))
print(f"\n  Starting on port {port}...")
print(f"  Provider: {db_provider} ✓")

import uvicorn
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    reload=False,
)
