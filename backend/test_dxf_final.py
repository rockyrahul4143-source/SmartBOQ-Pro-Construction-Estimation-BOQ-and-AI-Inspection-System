import sys, os
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")
os.environ["DATABASE_URL"] = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]   = "local-dev-secret-key"

from app.services.dxf_parser import parse_dxf_bytes

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"
with open(DXF, "rb") as f:
    raw = f.read()

result = parse_dxf_bytes(raw, units="mm")
d = result.to_dict()

print("=" * 50)
print("DXF PARSE RESULTS")
print("=" * 50)
print(f"Scale factor:    {d['scale_factor']} (units->metres)")
print(f"Wall length:     {d['total_wall_length_m']} m")
print(f"Floor area:      {d['total_floor_area_m2']} m²")
print(f"Rooms detected:  {len(d['rooms'])}")
print(f"Doors:           {d['num_doors']}")
print(f"Windows:         {d['num_windows']}")
print(f"Entity counts:   {d['entity_counts']}")
print()
for w in d['warnings']:
    print(f"  ℹ  {w}")
if d['rooms']:
    print("\nRooms:")
    for r in d['rooms']:
        print(f"  {r['name']}: {r['area_m2']} m²")
