"""
Seed standard SOR / Item Master data.
Based on CPWD DSR 2024 and common India civil engineering rates.
"""
from app.db.base import SessionLocal
from app.models.sor import SORItem, WorkCategory, RateSource

SOR_DATA = [
    # ── EARTHWORK ─────────────────────────────────────────────────────────
    ("EW-001","Earth excavation in foundation trenches/pits up to 1.5m depth","m3",380,WorkCategory.EARTHWORK,"volume","L × W × D × Nos = Volume m³","excavation_volume"),
    ("EW-002","Earth excavation 1.5m to 3.0m depth","m3",460,WorkCategory.EARTHWORK,"volume","L × W × D × Nos = Volume m³",None),
    ("EW-003","Earth filling in layers including watering and ramming","m3",220,WorkCategory.EARTHWORK,"volume","L × W × D = Volume m³",None),
    ("EW-004","Disposal of excavated earth (lead 50m)","m3",120,WorkCategory.EARTHWORK,"volume",None,None),

    # ── PCC ───────────────────────────────────────────────────────────────
    ("PCC-001","PCC M10 (1:3:6) in foundation","m3",4800,WorkCategory.PCC,"volume","L × W × thickness × Nos = Volume m³","M10"),
    ("PCC-002","PCC M15 (1:2:4) in foundation","m3",5400,WorkCategory.PCC,"volume","L × W × thickness = Volume m³","M15"),
    ("PCC-003","PCC M10 under floors (bed concrete)","m3",4600,WorkCategory.PCC,"volume","Area × thickness = Volume m³","M10"),

    # ── RCC ───────────────────────────────────────────────────────────────
    ("RCC-001","RCC M20 in isolated footings","m3",7200,WorkCategory.RCC,"volume","L × W × D × Nos = Volume m³","M20"),
    ("RCC-002","RCC M20 in columns","m3",8500,WorkCategory.RCC,"volume","L × W × H × Nos = Volume m³","M20"),
    ("RCC-003","RCC M20 in beams","m3",8200,WorkCategory.RCC,"volume","W × D × Length × Nos = Volume m³","M20"),
    ("RCC-004","RCC M20 in slabs","m3",7800,WorkCategory.RCC,"volume","L × W × thickness × Nos = Volume m³","M20"),
    ("RCC-005","RCC M25 in columns","m3",9000,WorkCategory.RCC,"volume","L × W × H × Nos = Volume m³","M25"),
    ("RCC-006","RCC M25 in beams","m3",8800,WorkCategory.RCC,"volume","W × D × Length × Nos = Volume m³","M25"),
    ("RCC-007","RCC M25 in slabs","m3",8500,WorkCategory.RCC,"volume","L × W × thickness = Volume m³","M25"),
    ("RCC-008","RCC M20 in staircase","m3",9200,WorkCategory.RCC,"volume",None,"M20"),
    ("RCC-009","RCC M20 in retaining walls","m3",8000,WorkCategory.RCC,"volume",None,"M20"),

    # ── REINFORCEMENT ──────────────────────────────────────────────────────
    ("STL-001","High yield deformed (HYD) bars Fe-500 in footings","kg",68,WorkCategory.REINFORCEMENT,"weight","Volume m³ × density(7850) × steel% = kg",None),
    ("STL-002","HYSD Fe-500 bars in columns","kg",70,WorkCategory.REINFORCEMENT,"weight","Volume m³ × density(7850) × steel% = kg",None),
    ("STL-003","HYSD Fe-500 bars in beams","kg",70,WorkCategory.REINFORCEMENT,"weight","Volume m³ × density(7850) × steel% = kg",None),
    ("STL-004","HYSD Fe-500 bars in slabs","kg",68,WorkCategory.REINFORCEMENT,"weight","Volume m³ × density(7850) × steel% = kg",None),
    ("STL-005","MS binding wire 16G","kg",85,WorkCategory.REINFORCEMENT,"weight",None,None),

    # ── FORMWORK ───────────────────────────────────────────────────────────
    ("FW-001","Centering and shuttering for columns","m2",420,WorkCategory.FORMWORK,"area","Perimeter × Height × Nos = Area m²",None),
    ("FW-002","Centering and shuttering for beams","m2",380,WorkCategory.FORMWORK,"area","(2D + W) × Length × Nos = Area m²",None),
    ("FW-003","Centering and shuttering for slabs","m2",320,WorkCategory.FORMWORK,"area","L × W × Nos = Area m²",None),
    ("FW-004","Centering and shuttering for footings","m2",280,WorkCategory.FORMWORK,"area","Perimeter × D × Nos = Area m²",None),
    ("FW-005","Centering and shuttering for staircase","m2",550,WorkCategory.FORMWORK,"area",None,None),

    # ── MASONRY ────────────────────────────────────────────────────────────
    ("MAS-001","Brick masonry 1:6 CM in superstructure 230mm thick","m3",4800,WorkCategory.MASONRY,"volume","L × H × 0.23 × Nos – openings = Volume m³",None),
    ("MAS-002","Brick masonry 1:6 CM 115mm thick","m3",5200,WorkCategory.MASONRY,"volume","L × H × 0.115 × Nos – openings = Volume m³",None),
    ("MAS-003","AAC block masonry 1:4 CM 200mm thick","m3",4200,WorkCategory.MASONRY,"volume","L × H × 0.20 × Nos – openings = Volume m³",None),
    ("MAS-004","AAC block masonry 1:4 CM 100mm thick","m3",4600,WorkCategory.MASONRY,"volume","L × H × 0.10 × Nos = Volume m³",None),
    ("MAS-005","Brick soling 115mm thick in foundation","m2",680,WorkCategory.MASONRY,"area","L × W × Nos = Area m²",None),

    # ── PLASTER ────────────────────────────────────────────────────────────
    ("PLS-001","Cement plaster external 1:6 20mm thick","m2",220,WorkCategory.PLASTER,"area","L × H × Nos – openings = Area m²",None),
    ("PLS-002","Cement plaster internal 1:4 12mm thick","m2",185,WorkCategory.PLASTER,"area","L × H × Nos – openings = Area m²",None),
    ("PLS-003","Cement plaster ceiling 1:4 12mm thick","m2",200,WorkCategory.PLASTER,"area","L × W × Nos = Area m²",None),
    ("PLS-004","Sand face plaster external 20mm","m2",260,WorkCategory.PLASTER,"area",None,None),
    ("PLS-005","Waterproof cement plaster 12mm (1:2)","m2",320,WorkCategory.PLASTER,"area",None,None),

    # ── FLOORING ───────────────────────────────────────────────────────────
    ("FLR-001","Vitrified floor tiles 600×600mm in CM 1:4","m2",950,WorkCategory.FLOORING,"area","L × W × Nos + 10% wastage = Area m²",None),
    ("FLR-002","Ceramic floor tiles 300×300mm in CM 1:4","m2",750,WorkCategory.FLOORING,"area","L × W × Nos = Area m²",None),
    ("FLR-003","Marble flooring 18mm in CM 1:4","m2",1800,WorkCategory.FLOORING,"area","L × W × Nos = Area m²",None),
    ("FLR-004","Kotah stone flooring 25mm","m2",650,WorkCategory.FLOORING,"area","L × W × Nos = Area m²",None),
    ("FLR-005","Ceramic wall tiles 300×450mm","m2",850,WorkCategory.FLOORING,"area","L × H × Nos = Area m²",None),
    ("FLR-006","IPS floor 40mm thick 1:2:4","m2",380,WorkCategory.FLOORING,"area",None,None),

    # ── WATERPROOFING ──────────────────────────────────────────────────────
    ("WPF-001","Integral waterproofing treatment to roof slab","m2",480,WorkCategory.WATERPROOFING,"area","L × W × Nos = Area m²",None),
    ("WPF-002","Bituminous felt waterproofing 2 layers","m2",620,WorkCategory.WATERPROOFING,"area",None,None),
    ("WPF-003","APP modified bitumen membrane waterproofing","m2",850,WorkCategory.WATERPROOFING,"area",None,None),
    ("WPF-004","Crystalline waterproofing to basement walls","m2",750,WorkCategory.WATERPROOFING,"area",None,None),

    # ── PAINTING ───────────────────────────────────────────────────────────
    ("PNT-001","Wall putty + 2 coats emulsion paint internal","m2",145,WorkCategory.PAINTING,"area","L × H × Nos – openings = Area m²",None),
    ("PNT-002","Exterior emulsion paint 2 coats (weather coat)","m2",160,WorkCategory.PAINTING,"area","L × H × Nos – openings = Area m²",None),
    ("PNT-003","OBD white washing 2 coats","m2",55,WorkCategory.PAINTING,"area",None,None),
    ("PNT-004","Enamel paint 2 coats to woodwork","m2",180,WorkCategory.PAINTING,"area",None,None),
    ("PNT-005","Primer + 2 coats enamel to MS grills","m2",220,WorkCategory.PAINTING,"area",None,None),

    # ── DOORS & WINDOWS ────────────────────────────────────────────────────
    ("DW-001","Flush door 35mm solid core (per door)","no",4800,WorkCategory.DOORS_WINDOWS,"number","Nos = Count",None),
    ("DW-002","Hardwood panel door 45mm","no",7500,WorkCategory.DOORS_WINDOWS,"number","Nos = Count",None),
    ("DW-003","Aluminium sliding window (per m²)","m2",1850,WorkCategory.DOORS_WINDOWS,"area","W × H × Nos = Area m²",None),
    ("DW-004","uPVC casement window (per m²)","m2",2200,WorkCategory.DOORS_WINDOWS,"area","W × H × Nos = Area m²",None),
    ("DW-005","MS rolling shutter (per m²)","m2",1650,WorkCategory.DOORS_WINDOWS,"area","W × H × Nos = Area m²",None),

    # ── PLUMBING ───────────────────────────────────────────────────────────
    ("PLB-001","uPVC SWR pipe 110mm dia per metre","m",320,WorkCategory.PLUMBING,"length","Length × Nos = metres",None),
    ("PLB-002","uPVC pressure pipe 63mm dia per metre","m",185,WorkCategory.PLUMBING,"length","Length × Nos = metres",None),
    ("PLB-003","CPVC hot/cold pipe 25mm per metre","m",145,WorkCategory.PLUMBING,"length",None,None),
    ("PLB-004","Bib cock CP brass","no",780,WorkCategory.PLUMBING,"number","Nos = Count",None),
    ("PLB-005","Concealed cistern flush valve","no",3800,WorkCategory.PLUMBING,"number","Nos = Count",None),
    ("PLB-006","EWC wall hung with seat","no",6500,WorkCategory.PLUMBING,"number","Nos = Count",None),

    # ── ELECTRICAL ─────────────────────────────────────────────────────────
    ("ELC-001","Conduit wiring FR 2.5mm² per metre (point)","point",850,WorkCategory.ELECTRICAL,"number","Nos = Count",None),
    ("ELC-002","MCB distribution board 12-way","no",4200,WorkCategory.ELECTRICAL,"number","Nos = Count",None),
    ("ELC-003","Earthing GI strip 25×3mm","m",180,WorkCategory.ELECTRICAL,"length",None,None),

    # ── ROAD ───────────────────────────────────────────────────────────────
    ("RD-001","WBM sub-base 100mm compacted","m2",280,WorkCategory.ROAD,"area","L × W × Nos = Area m²",None),
    ("RD-002","DBM bituminous concrete 40mm","m2",680,WorkCategory.ROAD,"area","L × W × Nos = Area m²",None),
    ("RD-003","Interlocking paver blocks 80mm","m2",720,WorkCategory.ROAD,"area","L × W × Nos = Area m²",None),
    ("RD-004","Kerb stone 150×300mm precast","m",380,WorkCategory.ROAD,"length","Length × Nos = metres",None),
    ("RD-005","Pot hole repair hot mix (per m²)","m2",480,WorkCategory.ROAD,"area","L × W × Nos = Area m²",None),
]

def seed_sor(db) -> int:
    count = 0
    for code, desc, unit, rate, cat, ftype, fnote, mix in SOR_DATA:
        if not db.query(SORItem).filter(SORItem.item_code == code).first():
            db.add(SORItem(
                item_code=code, description=desc, unit=unit,
                basic_rate=float(rate), category=cat,
                formula_type=ftype, formula_note=fnote,
                mix_design=mix,
                rate_source=RateSource.CPWD_DSR, rate_year=2024,
                rate_location="India",
                is_active=True, is_system=True,
                tags=f"{cat.value},{code.split('-')[0].lower()}",
            ))
            count += 1
    db.commit()
    return count


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = seed_sor(db)
        print(f"Seeded {n} SOR items")
    finally:
        db.close()
