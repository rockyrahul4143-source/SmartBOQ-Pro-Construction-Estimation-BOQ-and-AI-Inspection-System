"""Deep inspect: strip binary, parse with ezdxf, show all entity types per layer."""
import sys, io, re
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")
import ezdxf

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"

with open(DXF, "rb") as f:
    raw = f.read()

text = raw.decode("cp1252", errors="replace")
lines = text.splitlines(keepends=True)

# Strip binary 310 group codes and their data
clean = []
i = 0
while i < len(lines):
    stripped = lines[i].strip()
    if stripped == "310":
        i += 2   # skip code + hex data line
        continue
    clean.append(lines[i])
    i += 1

cleaned_text = "".join(clean)
print(f"Original lines: {len(lines)}, After strip: {len(clean)}")

# Now parse
try:
    doc = ezdxf.read(io.StringIO(cleaned_text))
    print("ezdxf.read: SUCCESS")
except Exception as e:
    print(f"ezdxf.read failed: {e}")
    sys.exit(1)

msp = doc.modelspace()
entities = list(msp)
print(f"Total entities in modelspace: {len(entities)}")

# Group by layer + type
from collections import defaultdict
layer_types = defaultdict(lambda: defaultdict(int))
for e in entities:
    try:
        layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
        etype = e.dxftype()
        layer_types[layer][etype] += 1
    except Exception:
        pass

print("\n=== Entities per layer ===")
for layer in sorted(layer_types.keys()):
    types_str = ", ".join(f"{t}:{n}" for t, n in sorted(layer_types[layer].items()))
    print(f"  Layer '{layer}': {types_str}")

# Show LINE details from each layer (first 3)
print("\n=== Sample LINE coords per layer ===")
shown = defaultdict(int)
for e in entities:
    try:
        if e.dxftype() == "LINE":
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
            if shown[layer] < 2:
                s = (round(e.dxf.start.x,1), round(e.dxf.start.y,1))
                end = (round(e.dxf.end.x,1), round(e.dxf.end.y,1))
                import math
                length = math.sqrt((end[0]-s[0])**2 + (end[1]-s[1])**2)
                print(f"  Layer '{layer}': {s} -> {end}, length={length:.1f}")
                shown[layer] += 1
    except Exception:
        pass

# Show LWPOLYLINE details
print("\n=== LWPOLYLINE info ===")
shown_poly = defaultdict(int)
for e in entities:
    try:
        if e.dxftype() == "LWPOLYLINE":
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
            if shown_poly[layer] < 2:
                pts = list(e.get_points("xy"))
                closed = e.closed
                area = 0
                if closed and len(pts) >= 3:
                    n = len(pts)
                    area = abs(sum(pts[i][0]*pts[(i+1)%n][1]-pts[(i+1)%n][0]*pts[i][1] for i in range(n)))/2
                print(f"  Layer '{layer}': {len(pts)} pts, closed={closed}, area={area:.1f}")
                shown_poly[layer] += 1
    except Exception:
        pass

print("\n=== INSUNITS from header ===")
try:
    insunits = doc.header.get("$INSUNITS", "not set")
    print(f"  $INSUNITS = {insunits}")
    extmin = doc.header.get("$EXTMIN")
    extmax = doc.header.get("$EXTMAX")
    print(f"  $EXTMIN = {extmin}")
    print(f"  $EXTMAX = {extmax}")
except Exception as e:
    print(f"  Error: {e}")
