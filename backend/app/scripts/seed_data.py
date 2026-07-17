"""
Seed Data Script
================
Populates the database with:
  1. Admin user account
  2. Complete material database with 2024 PKR rates
  3. Sample project with building and estimates

Run: python -m app.scripts.seed_data
Or automatically on docker-compose startup via docker-compose.yml command.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime
from app.db.base import SessionLocal
from app.models.user import User, UserRole
from app.models.material import Material, MaterialCategory, MaterialUnit
from app.core.security import hash_password

# ── Material seed data (PKR rates, Pakistan market 2024) ──────────────────────
MATERIALS = [
    # Cement
    ("OPC-0001", "Ordinary Portland Cement (OPC 43 Grade)", MaterialCategory.CEMENT,  MaterialUnit.BAG,          900,   "Maple Leaf Cement",    "+92-42-111-627539"),
    ("OPC-0002", "Ordinary Portland Cement (OPC 53 Grade)", MaterialCategory.CEMENT,  MaterialUnit.BAG,          950,   "DG Khan Cement",       "+92-42-111-111-344"),
    ("WPC-0003", "White Cement",                            MaterialCategory.CEMENT,  MaterialUnit.BAG,          1800,  "Fecto Cement",         None),

    # Sand
    ("SND-0001", "Fine Sand (Zone II - Ravi)",              MaterialCategory.SAND,    MaterialUnit.CUBIC_METER,  3500,  "Local Supplier",       None),
    ("SND-0002", "Coarse Sand (Lawrencepur)",               MaterialCategory.SAND,    MaterialUnit.CUBIC_METER,  4200,  "Local Supplier",       None),
    ("SND-0003", "Plaster Sand (Sieved Fine)",              MaterialCategory.SAND,    MaterialUnit.CUBIC_METER,  4500,  "Local Supplier",       None),

    # Aggregate
    ("AGG-0001", "Crushed Stone Aggregate 3/4\"",           MaterialCategory.AGGREGATE, MaterialUnit.CUBIC_METER, 6500, "Attock Cement",       None),
    ("AGG-0002", "Crushed Stone Aggregate 1/2\"",           MaterialCategory.AGGREGATE, MaterialUnit.CUBIC_METER, 6800, "Local Quarry",        None),
    ("AGG-0003", "Bajri (Natural Gravel)",                  MaterialCategory.AGGREGATE, MaterialUnit.CUBIC_METER, 5500, "River Supplier",      None),

    # Steel
    ("STL-0001", "HYSD Deformed Bars 10mm (Grade 60)",     MaterialCategory.STEEL,   MaterialUnit.KG,           230,   "Ittefaq Steel",       "+92-42-35788000"),
    ("STL-0002", "HYSD Deformed Bars 12mm (Grade 60)",     MaterialCategory.STEEL,   MaterialUnit.KG,           228,   "Ittefaq Steel",       "+92-42-35788000"),
    ("STL-0003", "HYSD Deformed Bars 16mm (Grade 60)",     MaterialCategory.STEEL,   MaterialUnit.KG,           225,   "Mughal Steel",        "+92-42-35960800"),
    ("STL-0004", "HYSD Deformed Bars 20mm (Grade 60)",     MaterialCategory.STEEL,   MaterialUnit.KG,           222,   "Mughal Steel",        "+92-42-35960800"),
    ("STL-0005", "MS Binding Wire 16 Gauge",               MaterialCategory.STEEL,   MaterialUnit.KG,           300,   "Local Supplier",      None),

    # Bricks
    ("BRK-0001", "First Class Brick (9x4.5x3 inch)",       MaterialCategory.BRICK,   MaterialUnit.NUMBER,       18,    "Local Kiln",          None),
    ("BRK-0002", "Second Class Brick",                     MaterialCategory.BRICK,   MaterialUnit.NUMBER,       14,    "Local Kiln",          None),
    ("BRK-0003", "Engineering Brick (Blue)",               MaterialCategory.BRICK,   MaterialUnit.NUMBER,       45,    "Imported",            None),

    # Blocks
    ("BLK-0001", "AAC Block 600x200x200mm",                MaterialCategory.BLOCK,   MaterialUnit.NUMBER,       220,   "Bolan Cement",        None),
    ("BLK-0002", "Hollow Concrete Block 400x200x200mm",    MaterialCategory.BLOCK,   MaterialUnit.NUMBER,       95,    "Local Manufacturer",  None),
    ("BLK-0003", "Solid Concrete Block 400x200x100mm",     MaterialCategory.BLOCK,   MaterialUnit.NUMBER,       65,    "Local Manufacturer",  None),

    # Paint
    ("PNT-0001", "Weather Coat Exterior Paint (20L)",      MaterialCategory.PAINT,   MaterialUnit.LITER,        650,   "Berger Paints",       "+92-21-111-237437"),
    ("PNT-0002", "Emulsion Paint Interior (20L)",          MaterialCategory.PAINT,   MaterialUnit.LITER,        480,   "Berger Paints",       "+92-21-111-237437"),
    ("PNT-0003", "Primer (Water Based, 20L)",              MaterialCategory.PAINT,   MaterialUnit.LITER,        320,   "ICI Paints",          None),
    ("PNT-0004", "Textured Paint (20L)",                   MaterialCategory.PAINT,   MaterialUnit.LITER,        750,   "Nippon Paint",        None),

    # Tiles
    ("TIL-0001", "Glazed Floor Tile 600x600mm",            MaterialCategory.TILE,    MaterialUnit.SQUARE_METER, 1800,  "Master Tiles",        "+92-52-3550101"),
    ("TIL-0002", "Vitrified Floor Tile 600x600mm",         MaterialCategory.TILE,    MaterialUnit.SQUARE_METER, 2200,  "Shabbir Tiles",       None),
    ("TIL-0003", "Ceramic Wall Tile 300x450mm",            MaterialCategory.TILE,    MaterialUnit.SQUARE_METER, 1400,  "Master Tiles",        "+92-52-3550101"),
    ("TIL-0004", "Porcelain Tile 800x800mm (Imported)",    MaterialCategory.TILE,    MaterialUnit.SQUARE_METER, 4500,  "Al-Murad Tiles",      None),
    ("TIL-0005", "Marble Tile (Ziarat White, 30mm thick)", MaterialCategory.TILE,    MaterialUnit.SQUARE_METER, 3200,  "Marble Palace",       None),

    # Waterproofing
    ("WPF-0001", "Integral Waterproofing Compound",        MaterialCategory.WATERPROOFING, MaterialUnit.KG,     450,   "Dr. Fixit",           None),
    ("WPF-0002", "Bituminous Coating (Brush Applied)",     MaterialCategory.WATERPROOFING, MaterialUnit.LITER,  380,   "Conpro Pakistan",     None),
    ("WPF-0003", "Crystalline Waterproofing Powder",       MaterialCategory.WATERPROOFING, MaterialUnit.KG,     800,   "PENETRON",            None),

    # Wood
    ("WOD-0001", "Deodar Timber (1st quality, 1 CFT)",     MaterialCategory.WOOD,    MaterialUnit.CUBIC_METER,  95000, "Timber Market",       None),
    ("WOD-0002", "Kail Timber (2nd quality, 1 CFT)",       MaterialCategory.WOOD,    MaterialUnit.CUBIC_METER,  65000, "Timber Market",       None),
    ("WOD-0003", "Flush Door (2100x900mm, solid core)",    MaterialCategory.WOOD,    MaterialUnit.NUMBER,       12000, "Shezan Doors",        None),
    ("WOD-0004", "Panel Door (2100x900mm, hardwood)",      MaterialCategory.WOOD,    MaterialUnit.NUMBER,       18000, "Royal Doors",         None),

    # Glass
    ("GLS-0001", "Float Glass 5mm (per m²)",               MaterialCategory.GLASS,   MaterialUnit.SQUARE_METER, 1200, "AGC Glass",            None),
    ("GLS-0002", "Tempered Glass 10mm (per m²)",           MaterialCategory.GLASS,   MaterialUnit.SQUARE_METER, 3800, "Guardian Glass",       None),
    ("GLS-0003", "Aluminium Sliding Window (per m²)",      MaterialCategory.GLASS,   MaterialUnit.SQUARE_METER, 5500, "Rehman Windows",       None),

    # Electrical
    ("ELC-0001", "PVC Conduit 20mm (per m)",               MaterialCategory.ELECTRICAL, MaterialUnit.LINEAR_METER, 85,  "Pakistan Cables",    "+92-21-111-262253"),
    ("ELC-0002", "Electrical Wire 2.5mm² (100m roll)",     MaterialCategory.ELECTRICAL, MaterialUnit.LINEAR_METER, 55,  "Pakistan Cables",    None),
    ("ELC-0003", "Distribution Board 12-way",              MaterialCategory.ELECTRICAL, MaterialUnit.NUMBER,    12000, "Siemens Pakistan",    None),

    # Plumbing
    ("PLB-0001", "UPVC Pipe 4 inch (per m)",               MaterialCategory.PLUMBING, MaterialUnit.LINEAR_METER, 380, "Wavin Pakistan",      None),
    ("PLB-0002", "UPVC Pipe 2 inch (per m)",               MaterialCategory.PLUMBING, MaterialUnit.LINEAR_METER, 180, "Wavin Pakistan",      None),
    ("PLB-0003", "CP Water Tap (standard)",                MaterialCategory.PLUMBING, MaterialUnit.NUMBER,       2500, "Neymar Sanitary",     None),
    ("PLB-0004", "Closet (EWC, standard quality)",         MaterialCategory.PLUMBING, MaterialUnit.NUMBER,       8500, "Porta Sanitary",      None),
]


def seed_materials(db) -> int:
    count = 0
    for code, name, cat, unit, rate, supplier, contact in MATERIALS:
        existing = db.query(Material).filter(Material.material_code == code).first()
        if not existing:
            m = Material(
                material_code=code,
                name=name,
                category=cat,
                unit=unit,
                current_rate=float(rate),
                supplier_name=supplier,
                supplier_contact=contact,
                is_active=True,
                last_updated=datetime.utcnow(),
            )
            db.add(m)
            count += 1
    db.commit()
    return count


def seed_admin(db) -> bool:
    existing = db.query(User).filter(User.email == "admin@smartboq.com").first()
    if existing:
        return False
    admin = User(
        email="admin@smartboq.com",
        full_name="System Administrator",
        hashed_password=hash_password("Admin@1234"),
        role=UserRole.ADMIN,
        company="SmartBOQ Pro",
        designation="System Administrator",
        is_active=True,
        is_verified=True,
    )
    db.add(admin)

    # Demo estimation engineer
    demo = User(
        email="engineer@smartboq.com",
        full_name="Demo Engineer",
        hashed_password=hash_password("Engineer@1234"),
        role=UserRole.ESTIMATION_ENGINEER,
        company="ABC Construction",
        designation="Senior Estimation Engineer",
        is_active=True,
        is_verified=True,
    )
    db.add(demo)
    db.commit()
    return True


def run():
    print("🌱 SmartBOQ Pro — Seeding database...")
    db = SessionLocal()
    try:
        # Admin users
        created = seed_admin(db)
        if created:
            print("  ✅ Admin user:    admin@smartboq.com  /  Admin@1234")
            print("  ✅ Demo engineer: engineer@smartboq.com  /  Engineer@1234")
        else:
            print("  ℹ️  Admin user already exists — skipping")

        # Materials
        mat_count = seed_materials(db)
        if mat_count > 0:
            print(f"  ✅ {mat_count} materials seeded (2024 PKR rates)")
        else:
            print("  ℹ️  Materials already seeded — skipping")

        print("🚀 Seed complete!")
    except Exception as e:
        db.rollback()
        print(f"  ❌ Seed error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
