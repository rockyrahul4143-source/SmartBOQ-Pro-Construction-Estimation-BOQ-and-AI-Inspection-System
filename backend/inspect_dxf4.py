"""The DXF has 0 entities in layouts AND blocks after stripping 310 codes.
This means the stripping is removing too much. Let's find what's really there."""
import sys
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"

with open(DXF, "rb") as f:
    raw = f.read()

text = raw.decode("cp1252", errors="replace")
lines = text.splitlines()

# Find ENTITIES section
entities_start = None
entities_end   = None
for i, l in enumerate(lines):
    if l.strip() == "ENTITIES":
        # Next "0\nSECTION" pair identifies section start
        entities_start = i
    if entities_start and l.strip() == "ENDSEC" and i > entities_start + 5:
        entities_end = i
        break

print(f"ENTITIES section: lines {entities_start} to {entities_end}")
if entities_start and entities_end:
    section = lines[entities_start:entities_end]
    print(f"Lines in ENTITIES section: {len(section)}")
    # Count entity types
    entity_types = {}
    for j, l in enumerate(section):
        if l.strip() == "0" and j+1 < len(section):
            etype = section[j+1].strip()
            if etype.isupper() and len(etype) > 1 and not etype.startswith("$"):
                entity_types[etype] = entity_types.get(etype, 0) + 1
    print(f"Entity types: {dict(sorted(entity_types.items(), key=lambda x: -x[1])[:20])}")
    print(f"\nFirst 40 lines of ENTITIES section:")
    for i, l in enumerate(section[:40]):
        print(f"  {entities_start+i}: {repr(l[:80])}")
else:
    print("Could not find ENTITIES section!")
    # Find all SECTION names
    print("All section names found:")
    for i, l in enumerate(lines):
        if l.strip() == "SECTION" and i+1 < len(lines) and lines[i-1].strip() == "0":
            print(f"  Line {i}: SECTION '{lines[i+2].strip() if i+2 < len(lines) else '?'}'")

# Also check for ACDSDATA section which may contain the actual drawing data
print("\n=== Looking for binary/zip content ===")
for i, l in enumerate(lines):
    if l.strip() == "310" and i+1 < len(lines):
        hex_data = lines[i+1].strip()
        if hex_data.startswith("504B"):  # PK = ZIP file magic
            print(f"  Line {i}: ZIP file embedded at group 310 ('{hex_data[:40]}...')")
            break
        elif i < 39200:
            print(f"  Line {i}: binary group 310: '{hex_data[:40]}'")
