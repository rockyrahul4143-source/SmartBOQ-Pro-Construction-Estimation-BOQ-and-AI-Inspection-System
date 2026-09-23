"""
SmartBOQ Pro — Render.com Production Startup
"""
import os, sys, subprocess, pathlib, traceback

# ── Environment defaults ─────────────────────────────
os.environ.setdefault("APP_ENV",    "production")
os.environ.setdefault("DEBUG",      "false")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")

os.makedirs("/tmp/uploads",             exist_ok=True)
os.makedirs("/tmp/uploads/inspections", exist_ok=True)

print("=" * 55)
print("  SmartBOQ Pro — Production Startup")
print("=" * 55)
sys.stdout.flush()

db_url = os.getenv("DATABASE_URL", "")
secret  = os.getenv("SECRET_KEY", "")

print(f"  DATABASE_URL : {'SET' if db_url else 'MISSING'}")
print(f"  SECRET_KEY   : {'SET' if secret  else 'MISSING'}")
sys.stdout.flush()

if not db_url:
    print("\n  FATAL: DATABASE_URL not set.")
    print("  Go to Render → Environment → add DATABASE_URL")
    sys.exit(1)

# Fix URL scheme
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    print("  Fixed: postgres:// -> postgresql://")

# Neon SSL
if "neon.tech" in db_url and "sslmode" not in db_url:
    sep = "&" if "?" in db_url else "?"
    db_url = db_url + sep + "sslmode=require"
    print("  Added: sslmode=require (Neon)")

os.environ["DATABASE_URL"] = db_url
provider = "Neon" if "neon.tech" in db_url else "PostgreSQL"
print(f"  Provider: {provider}")
sys.stdout.flush()

# Add backend to path
BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))

# Step 1: Create tables
print("\n  [1/3] Creating tables...")
sys.stdout.flush()
try:
    from app.db.base import Base, engine
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    print("        Tables OK")
    sys.stdout.flush()
except Exception as e:
    print(f"        ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: Migrations
print("  [2/3] Migrations...")
sys.stdout.flush()
try:
    subprocess.run(["alembic", "stamp", "head"], capture_output=True, cwd=str(BASE))
    r = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True, cwd=str(BASE))
    if r.returncode == 0:
        print("        Migrations OK")
    else:
        print(f"        Note: {(r.stderr or '')[-200:]}")
except Exception as e:
    print(f"        Skipped: {e}")
sys.stdout.flush()

# Step 3: Seed
print("  [3/3] Seeding...")
sys.stdout.flush()
try:
    from app.scripts.seed_data import run as seed_run
    seed_run()
    print("        Seed OK")
except Exception as e:
    print(f"        Seed note: {e}")
sys.stdout.flush()

# Start server
port = int(os.getenv("PORT", 8000))
print(f"\n  Starting on port {port}...")
sys.stdout.flush()

import uvicorn
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    reload=False,
)
