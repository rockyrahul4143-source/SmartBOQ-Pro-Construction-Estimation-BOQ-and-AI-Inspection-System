"""
Local setup script — creates DB tables and seeds data on first run only.
Safe to run every time: skips drop/seed if DB already exists.
Run: python setup_local.py   (use Python 3.12 / QGIS Python)
"""
import sys, os

os.environ["DATABASE_URL"]    = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]      = "local-dev-secret-key-smartboq-pro-2024"
os.environ["ALLOWED_ORIGINS"] = "*"

# Use Python 3.12 user site-packages (fastapi, sqlalchemy etc. installed here)
import site
user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

from app.db.base import Base, engine
from app.models.user       import User, UserRole
from app.models.project    import Project, BuildingType, ProjectStatus
from app.models.building   import Building, Room
from app.models.material   import Material, MaterialCategory, MaterialUnit, MaterialRateHistory
from app.models.estimate   import Estimate, WorkType
from app.models.boq        import BOQ, BOQItem, BOQStatus
from app.models.report     import Report, ReportType, ReportFormat, AuditLog
from app.models.inspection import Inspection, InspectionType, SeverityLevel

db_path = "./smartboq.db"
first_run = not os.path.exists(db_path)

# Always create any missing tables (safe, does not drop existing ones)
print("  Checking database tables...")
Base.metadata.create_all(bind=engine)
print("  Tables OK")

if first_run:
    print("  First run detected — seeding data...")
    from app.scripts.seed_data import run
    run()
    print("\nSetup complete! Database initialised.")
else:
    print("  Database already exists — skipping seed (your data is safe).")
    print("\nSetup complete! Ready to start.")
