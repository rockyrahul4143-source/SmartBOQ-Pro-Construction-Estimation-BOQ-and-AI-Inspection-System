"""
SmartBOQ Pro — Render.com Production Startup
=============================================
Strategy:
  1. Use SQLAlchemy create_all() — always safe, never drops data
  2. Run alembic only as fallback for additive migrations
  3. Seed permanent users + materials
  4. Start uvicorn
"""
import os, sys, subprocess, pathlib

# ── Environment ───────────────────────────────────────
os.environ.setdefault("APP_ENV",    "production")
os.environ.setdefault("DEBUG",      "false")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

os.makedirs("/tmp/uploads",            exist_ok=True)
os.makedirs("/tmp/uploads/inspections", exist_ok=True)

print("=" * 50)
print("  SmartBOQ Pro — Render Production Startup")
print("=" * 50)

db_url = os.getenv("DATABASE_URL", "")
secret  = os.getenv("SECRET_KEY", "")

print(f"  DATABASE_URL : {'SET ✓' if db_url else 'MISSING ✗ — set on Render dashboard'}")
print(f"  SECRET_KEY   : {'SET ✓' if secret  else 'MISSING ✗ — set on Render dashboard'}")

if not db_url:
    print("\n  FATAL: DATABASE_URL not set. Add it in Render → Environment.\n")
    sys.exit(1)

# Render gives postgres:// but SQLAlchemy needs postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    os.environ["DATABASE_URL"] = db_url
    print("  Fixed postgres:// → postgresql://")

# ── Add backend to path ───────────────────────────────
BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))

# ── Step 1: create_all (safe, idempotent) ─────────────
print("\n  [1/3] Creating tables (create_all)...")
try:
    from app.db.base import Base, engine
    import app.models  # noqa — registers all models
    Base.metadata.create_all(bind=engine)
    print("        Tables OK ✓")
except Exception as e:
    print(f"        create_all error: {e}")
    sys.exit(1)

# ── Step 2: alembic migrate (stamp if first time) ─────
print("  [2/3] Running alembic migrations...")
try:
    # Stamp head first so alembic knows current state if fresh DB
    r = subprocess.run(
        ["alembic", "stamp", "head"],
        capture_output=True, text=True, cwd=str(BASE)
    )
    # Then upgrade — safe if already at head
    r2 = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=str(BASE)
    )
    if r2.returncode == 0:
        print("        Migrations OK ✓")
    else:
        # Non-fatal — create_all already ran
        print(f"        Migration note: {r2.stderr[-300:] if r2.stderr else 'none'}")
        print("        (Continuing — tables created via create_all)")
except FileNotFoundError:
    print("        alembic not found — skipping (tables via create_all)")
except Exception as e:
    print(f"        Migration skipped: {e}")

# ── Step 3: seed data ─────────────────────────────────
print("  [3/3] Seeding data...")
try:
    from app.scripts.seed_data import run as seed_run
    seed_run()
    print("        Seed OK ✓")
except Exception as e:
    print(f"        Seed note: {e}")

# ── Start server ──────────────────────────────────────
port = int(os.getenv("PORT", 8000))
print(f"\n  Starting on port {port}...")
print(f"  API Docs: https://<your-render-url>/docs\n")

import uvicorn
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    reload=False,
)
