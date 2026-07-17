import sys, os
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")
os.environ["DATABASE_URL"] = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"] = "local-dev-secret-key"

DXF_PATH = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"

with open(DXF_PATH, "rb") as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")
print(f"First 300 bytes (repr): {repr(raw[:300])}")
print()

# Check encoding
for enc in ["utf-8", "latin-1", "cp1252"]:
    try:
        text = raw[:500].decode(enc)
        print(f"Decodable as {enc}: YES — first line: {text.splitlines()[0][:80]}")
    except Exception as e:
        print(f"Decodable as {enc}: NO — {e}")

print()

# Check for binary content
binary_chars = sum(1 for b in raw[:5000] if b < 9 or (b > 13 and b < 32))
print(f"Binary bytes in first 5000: {binary_chars}")
print(f"Is likely binary DXF: {binary_chars > 50}")
print()

# Try ezdxf strategies
import ezdxf
from ezdxf import recover
import io

print("=== Testing ezdxf strategies ===")

# Strategy 1: direct read utf-8
try:
    doc = ezdxf.read(io.StringIO(raw.decode("utf-8", errors="replace")))
    print("Strategy 1 (utf-8 read): SUCCESS")
    msp = doc.modelspace()
    entities = list(msp)
    print(f"  Entities in modelspace: {len(entities)}")
    types = {}
    for e in entities:
        t = e.dxftype()
        types[t] = types.get(t, 0) + 1
    print(f"  Entity types: {dict(sorted(types.items(), key=lambda x: -x[1])[:10])}")
    
    # Check layers
    layers = [layer.dxf.name for layer in doc.layers]
    print(f"  Total layers: {len(layers)}")
    wall_layers = [l for l in layers if any(w in l.lower() for w in ["wall","walls","ext_wall","int_wall","partition"])]
    print(f"  Wall-related layers: {wall_layers}")
    all_layers_lower = sorted(set(l.lower() for l in layers))
    print(f"  All layers (lowercase, first 30): {all_layers_lower[:30]}")
except Exception as e:
    print(f"Strategy 1 (utf-8 read): FAILED — {e}")

# Strategy 2: recover
try:
    doc, auditor = recover.readbytes(raw)
    print(f"Strategy 2 (recover): SUCCESS, errors={len(auditor.errors)}")
    msp = doc.modelspace()
    entities = list(msp)
    print(f"  Entities: {len(entities)}")
    layers = [layer.dxf.name for layer in doc.layers]
    print(f"  Layers: {layers[:20]}")
except Exception as e:
    print(f"Strategy 2 (recover): FAILED — {e}")

print()
print("=== Testing our parser ===")
from app.services.dxf_parser import parse_dxf_bytes
result = parse_dxf_bytes(raw, units="mm")
d = result.to_dict()
print(f"Wall length: {d['total_wall_length_m']} m")
print(f"Floor area:  {d['total_floor_area_m2']} m2")
print(f"Doors:       {d['num_doors']}")
print(f"Windows:     {d['num_windows']}")
print(f"Rooms:       {len(d['rooms'])}")
print(f"Entities:    {d['entity_counts']}")
print(f"Warnings:    {d['warnings']}")
