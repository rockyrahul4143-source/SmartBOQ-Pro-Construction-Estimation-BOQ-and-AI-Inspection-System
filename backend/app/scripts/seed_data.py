"""
Seed Data Script
================
Populates the database with:
  1. Admin + Demo user accounts
  2. Complete material database — 2024 India INR market rates
     (Sources: CPWD DSR 2024, NBO India, market survey)

Run via setup_local.py on first launch.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime
from app.db.base import SessionLocal
from app.models.user import User, UserRole
from app.models.material import Material, MaterialCategory, MaterialUnit
from app.core.security import hash_password

# ══════════════════════════════════════════════════════════════════════════════
# MATERIAL SEED DATA — 2024 India INR Rates
# Format: (code, name, category, unit, rate_INR, supplier, contact)
# Rates based on: CPWD DSR 2024, NBO India, regional market survey
# ══════════════════════════════════════════════════════════════════════════════
MATERIALS = [

    # ── CEMENT ──────────────────────────────────────────────────────────────
    # OPC 43 Grade bag (50 kg) — Avg India retail 2024
    ("CEM-001", "OPC 43 Grade Cement (50 kg bag)",
     MaterialCategory.CEMENT, MaterialUnit.BAG,
     420, "UltraTech / ACC / Ambuja", "1800-200-1234"),

    # OPC 53 Grade bag (50 kg)
    ("CEM-002", "OPC 53 Grade Cement (50 kg bag)",
     MaterialCategory.CEMENT, MaterialUnit.BAG,
     440, "UltraTech Cement", "1800-200-1234"),

    # PPC (Portland Pozzolana Cement)
    ("CEM-003", "PPC Portland Pozzolana Cement (50 kg)",
     MaterialCategory.CEMENT, MaterialUnit.BAG,
     400, "Shree Cement / Wonder Cement", None),

    # White Cement
    ("CEM-004", "White Cement (50 kg bag)",
     MaterialCategory.CEMENT, MaterialUnit.BAG,
     780, "J K White Cement", None),

    # ── SAND ────────────────────────────────────────────────────────────────
    # River sand per cubic metre
    ("SND-001", "River Sand — Fine (Zone II)",
     MaterialCategory.SAND, MaterialUnit.CUBIC_METER,
     1800, "Local Sand Supplier", None),

    # M-Sand (Manufactured Sand) per m³
    ("SND-002", "M-Sand (Manufactured Sand)",
     MaterialCategory.SAND, MaterialUnit.CUBIC_METER,
     1400, "Local Quarry / Crusher", None),

    # Plaster Sand (sieved fine)
    ("SND-003", "Plaster Sand (Sieved Fine)",
     MaterialCategory.SAND, MaterialUnit.CUBIC_METER,
     2000, "Local Supplier", None),

    # ── AGGREGATE ────────────────────────────────────────────────────────────
    # 20mm Crushed Stone Aggregate per m³
    ("AGG-001", "Crushed Stone Aggregate 20mm (per m³)",
     MaterialCategory.AGGREGATE, MaterialUnit.CUBIC_METER,
     1600, "Local Stone Crusher", None),

    # 10mm Crushed Stone Aggregate per m³
    ("AGG-002", "Crushed Stone Aggregate 10mm (per m³)",
     MaterialCategory.AGGREGATE, MaterialUnit.CUBIC_METER,
     1700, "Local Stone Crusher", None),

    # 40mm Aggregate (road base / PCC)
    ("AGG-003", "Crushed Stone Aggregate 40mm (per m³)",
     MaterialCategory.AGGREGATE, MaterialUnit.CUBIC_METER,
     1500, "Local Stone Crusher", None),

    # ── STEEL / TMT BARS ────────────────────────────────────────────────────
    # Fe-500 TMT Bar 8mm per kg
    ("STL-001", "TMT Bar Fe-500 8mm (per kg)",
     MaterialCategory.STEEL, MaterialUnit.KG,
     68, "TATA Steel / JSW Steel", "1800-103-8282"),

    # Fe-500 TMT Bar 10mm per kg
    ("STL-002", "TMT Bar Fe-500 10mm (per kg)",
     MaterialCategory.STEEL, MaterialUnit.KG,
     67, "TATA Steel / JSW Steel", "1800-103-8282"),

    # Fe-500 TMT Bar 12mm per kg
    ("STL-003", "TMT Bar Fe-500 12mm (per kg)",
     MaterialCategory.STEEL, MaterialUnit.KG,
     66, "TATA Steel / Sail Steel", None),

    # Fe-500 TMT Bar 16mm per kg
    ("STL-004", "TMT Bar Fe-500 16mm (per kg)",
     MaterialCategory.STEEL, MaterialUnit.KG,
     65, "TATA Steel / Sail Steel", None),

    # Fe-500D TMT Bar 20mm per kg
    ("STL-005", "TMT Bar Fe-500D 20mm (per kg)",
     MaterialCategory.STEEL, MaterialUnit.KG,
     65, "TATA Steel", None),

    # MS Binding Wire 16G per kg
    ("STL-006", "MS Binding Wire 16 Gauge (per kg)",
     MaterialCategory.STEEL, MaterialUnit.KG,
     80, "Local Supplier", None),

    # ── BRICKS ───────────────────────────────────────────────────────────────
    # First Class Modular Brick (230x110x70mm) per number
    ("BRK-001", "First Class Modular Brick (230x110x70mm)",
     MaterialCategory.BRICK, MaterialUnit.NUMBER,
     10, "Local Brick Kiln", None),

    # Second Class Brick
    ("BRK-002", "Second Class Brick",
     MaterialCategory.BRICK, MaterialUnit.NUMBER,
     7, "Local Brick Kiln", None),

    # Fly Ash Brick (per number)
    ("BRK-003", "Fly Ash Brick (230x110x70mm)",
     MaterialCategory.BRICK, MaterialUnit.NUMBER,
     8, "ACC / Local Manufacturer", None),

    # ── BLOCKS ───────────────────────────────────────────────────────────────
    # AAC Block 600x200x200mm per number
    ("BLK-001", "AAC Block 600x200x200mm",
     MaterialCategory.BLOCK, MaterialUnit.NUMBER,
     55, "Siporex / Biltech AAC", None),

    # Hollow Concrete Block (HCB) 400x200x200mm
    ("BLK-002", "Hollow Concrete Block 400x200x200mm",
     MaterialCategory.BLOCK, MaterialUnit.NUMBER,
     45, "Local Manufacturer", None),

    # Solid Concrete Block 400x200x100mm
    ("BLK-003", "Solid Concrete Block 400x200x100mm",
     MaterialCategory.BLOCK, MaterialUnit.NUMBER,
     35, "Local Manufacturer", None),

    # ── PAINT ─────────────────────────────────────────────────────────────────
    # Exterior Emulsion Paint per litre
    ("PNT-001", "Exterior Emulsion / Weather Coat Paint (per litre)",
     MaterialCategory.PAINT, MaterialUnit.LITER,
     220, "Asian Paints / Berger", "1800-209-5678"),

    # Interior Emulsion Paint per litre
    ("PNT-002", "Interior Emulsion Paint (per litre)",
     MaterialCategory.PAINT, MaterialUnit.LITER,
     160, "Asian Paints / Nerolac", "1800-209-5678"),

    # Primer (Water Based) per litre
    ("PNT-003", "Wall Primer Water Based (per litre)",
     MaterialCategory.PAINT, MaterialUnit.LITER,
     90, "Asian Paints / Berger", None),

    # Enamel Paint per litre
    ("PNT-004", "Synthetic Enamel Paint (per litre)",
     MaterialCategory.PAINT, MaterialUnit.LITER,
     200, "Nerolac / Kansai", None),

    # Textured Paint per litre
    ("PNT-005", "Textured / Texture Coat Paint (per litre)",
     MaterialCategory.PAINT, MaterialUnit.LITER,
     280, "Asian Paints Apex", None),

    # ── TILES ─────────────────────────────────────────────────────────────────
    # Vitrified Floor Tile 600x600mm per m²
    ("TIL-001", "Vitrified Floor Tile 600x600mm (per m²)",
     MaterialCategory.TILE, MaterialUnit.SQUARE_METER,
     650, "Kajaria / Somany / Orient", "1800-102-5530"),

    # Ceramic Wall Tile 300x450mm per m²
    ("TIL-002", "Ceramic Wall Tile 300x450mm (per m²)",
     MaterialCategory.TILE, MaterialUnit.SQUARE_METER,
     480, "Kajaria / Johnson Tiles", None),

    # Digital Vitrified Tile 800x800mm per m²
    ("TIL-003", "Digital Vitrified Tile 800x800mm (per m²)",
     MaterialCategory.TILE, MaterialUnit.SQUARE_METER,
     1200, "Kajaria / RAK Ceramics", None),

    # Kotah Stone per m²
    ("TIL-004", "Kotah Stone Flooring (per m²)",
     MaterialCategory.TILE, MaterialUnit.SQUARE_METER,
     380, "Rajasthan Stone Supplier", None),

    # Indian Marble (White) per m²
    ("TIL-005", "Indian Marble White 18mm (per m²)",
     MaterialCategory.TILE, MaterialUnit.SQUARE_METER,
     900, "Rajasthan Marble Dealer", None),

    # ── WATERPROOFING ──────────────────────────────────────────────────────────
    # Integral waterproofing compound per kg
    ("WPF-001", "Integral Waterproofing Compound (per kg)",
     MaterialCategory.WATERPROOFING, MaterialUnit.KG,
     55, "Dr. Fixit / Fosroc / SikaIndiaF", None),

    # Crystalline waterproofing powder per kg
    ("WPF-002", "Crystalline Waterproofing Powder (per kg)",
     MaterialCategory.WATERPROOFING, MaterialUnit.KG,
     350, "PENETRON / Dr. Fixit", None),

    # Bituminous Waterproofing Coating per litre
    ("WPF-003", "Bituminous Waterproofing Coating (per litre)",
     MaterialCategory.WATERPROOFING, MaterialUnit.LITER,
     120, "Fosroc / SikaIndia", None),

    # ── WOOD ──────────────────────────────────────────────────────────────────
    # Teak Wood (Sagwan) per cubic foot
    ("WOD-001", "Teak Wood (Sagwan) — per Cubic Foot",
     MaterialCategory.WOOD, MaterialUnit.CUBIC_METER,
     120000, "Timber Market", None),

    # Sal Wood per cubic foot
    ("WOD-002", "Sal Wood — per Cubic Foot",
     MaterialCategory.WOOD, MaterialUnit.CUBIC_METER,
     45000, "Timber Market", None),

    # Flush Door (2100x900mm solid core)
    ("WOD-003", "Flush Door 2100x900mm Solid Core",
     MaterialCategory.WOOD, MaterialUnit.NUMBER,
     4500, "Century Ply / Greenply", None),

    # Plywood 18mm BWR per sheet (8x4 ft)
    ("WOD-004", "BWR Plywood 18mm (8x4 ft sheet)",
     MaterialCategory.WOOD, MaterialUnit.NUMBER,
     2800, "Century Ply / Kitply", None),

    # ── GLASS ─────────────────────────────────────────────────────────────────
    # Float Glass 5mm per m²
    ("GLS-001", "Float Glass 5mm (per m²)",
     MaterialCategory.GLASS, MaterialUnit.SQUARE_METER,
     350, "Saint Gobain / Asahi India", None),

    # Tempered Glass 10mm per m²
    ("GLS-002", "Tempered Glass 10mm (per m²)",
     MaterialCategory.GLASS, MaterialUnit.SQUARE_METER,
     1200, "Saint Gobain India", None),

    # Aluminium Window Frame per m²
    ("GLS-003", "Aluminium Sliding Window (per m²)",
     MaterialCategory.GLASS, MaterialUnit.SQUARE_METER,
     1800, "Jindal Aluminium / Hindalco", None),

    # ── ELECTRICAL ──────────────────────────────────────────────────────────
    # PVC Conduit 20mm per metre
    ("ELC-001", "PVC Conduit 20mm (per metre)",
     MaterialCategory.ELECTRICAL, MaterialUnit.LINEAR_METER,
     28, "Havells / Finolex / Polycab", "1800-103-5678"),

    # Electrical Wire 2.5mm² per metre
    ("ELC-002", "FR Wire 2.5mm² (per metre)",
     MaterialCategory.ELECTRICAL, MaterialUnit.LINEAR_METER,
     35, "Polycab / Havells / Finolex", None),

    # MCB Distribution Board 12-way
    ("ELC-003", "MCB Distribution Board 12-way",
     MaterialCategory.ELECTRICAL, MaterialUnit.NUMBER,
     3500, "Legrand / Schneider / Havells", None),

    # ── PLUMBING ──────────────────────────────────────────────────────────────
    # UPVC Pipe 110mm (4 inch) per metre
    ("PLB-001", "UPVC SWR Pipe 110mm (per metre)",
     MaterialCategory.PLUMBING, MaterialUnit.LINEAR_METER,
     220, "Astral Pipes / Supreme / Finolex", None),

    # UPVC Pipe 63mm (2.5 inch) per metre
    ("PLB-002", "UPVC Pressure Pipe 63mm (per metre)",
     MaterialCategory.PLUMBING, MaterialUnit.LINEAR_METER,
     120, "Astral Pipes / Supreme", None),

    # CPVC Hot/Cold Pipe 25mm per metre
    ("PLB-003", "CPVC Hot & Cold Pipe 25mm (per metre)",
     MaterialCategory.PLUMBING, MaterialUnit.LINEAR_METER,
     95, "Astral CPVC / FlowGuard", None),

    # CP Bib Cock (Tap)
    ("PLB-004", "CP Bib Cock / Tap (Standard)",
     MaterialCategory.PLUMBING, MaterialUnit.NUMBER,
     650, "Jaquar / Hindware / Cera", "1800-103-5527"),

    # EWC Toilet (standard quality)
    ("PLB-005", "EWC Toilet (Standard Quality)",
     MaterialCategory.PLUMBING, MaterialUnit.NUMBER,
     4500, "Cera / Parryware / Hindware", None),

    # Washbasin (standard)
    ("PLB-006", "Washbasin 550mm (Standard)",
     MaterialCategory.PLUMBING, MaterialUnit.NUMBER,
     2200, "Parryware / Hindware / Cera", None),
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


# Permanent users — always created, never deleted
# Add any user here who should always have access
PERMANENT_USERS = [
    ("admin@smartboq.com",       "System Administrator",    "Admin@1234",    UserRole.ADMIN,                "SmartBOQ Pro",           "System Administrator"),
    ("rockyrahul4143@gmail.com", "Rahul Singh",             "Rocky@1234",    UserRole.ADMIN,                "SmartBOQ Pro",           "Admin"),
    ("rrana732672@gmail.com",    "Rahul Rana",              "Rana123@#",     UserRole.ADMIN,                "SmartBOQ Pro",           "Admin"),
    ("engineer@smartboq.com",   "Demo Engineer",            "Engineer@1234", UserRole.ESTIMATION_ENGINEER,  "ABC Construction",       "Senior Estimation Engineer"),
]


def seed_admin(db) -> int:
    """Create permanent users. Safe to call multiple times — skips if exists."""
    count = 0
    for email, full_name, pwd, role, company, designation in PERMANENT_USERS:
        if not db.query(User).filter(User.email == email).first():
            db.add(User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(pwd),
                role=role,
                company=company,
                designation=designation,
                is_active=True,
                is_verified=True,
            ))
            count += 1
    db.commit()
    return count


def run():
    print("🌱 SmartBOQ Pro — Seeding database...")
    db = SessionLocal()
    try:
        # Permanent users — always ensured
        added = seed_admin(db)
        if added > 0:
            print(f"  ✅ {added} user(s) created")
            for email, _, pwd, _, _, _ in PERMANENT_USERS:
                print(f"     {email}  /  {pwd}")
        else:
            print("  ℹ️  All users already exist — skipping")

        mat_count = seed_materials(db)
        if mat_count > 0:
            print(f"  ✅ {mat_count} materials seeded (2024 India INR rates)")
        else:
            print("  ℹ️  Materials already seeded — skipping")

        # Seed SOR / Item Master
        try:
            from app.scripts.seed_sor import seed_sor
            sor_count = seed_sor(db)
            if sor_count > 0:
                print(f"  ✅ {sor_count} SOR items seeded (CPWD DSR 2024)")
            else:
                print("  ℹ️  SOR items already seeded — skipping")
        except Exception as e:
            print(f"  ⚠️  SOR seed skipped: {e}")

        print("🚀 Seed complete!")
    except Exception as e:
        db.rollback()
        print(f"  ❌ Seed error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
