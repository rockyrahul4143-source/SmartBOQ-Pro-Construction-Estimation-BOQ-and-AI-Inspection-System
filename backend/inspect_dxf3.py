"""The modelspace is empty — entities are likely in paper space or blocks. Check all spaces."""
import sys, io
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")
import ezdxf
import math
from collections import defaultdict

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"

with open(DXF, "rb") as f:
    raw = f.read()

text = raw.decode("cp1252", errors="replace")
lines = text.splitlines(keepends=True)

# Strip 310 binary group codes
clean = []
i = 0
while i < len(lines):
    if lines[i].strip() == "310":
        i += 2
        continue
    clean.append(lines[i])
    i += 1

doc = ezdxf.read(io.StringIO("".join(clean)))

# Check ALL layouts / block definitions
print("=== All layouts ===")
for layout in doc.layouts:
    ents = list(layout)
    print(f"  Layout '{layout.name}': {len(ents)} entities")
    layer_count = defaultdict(int)
    for e in ents:
        try:
            layer_count[e.dxf.layer] += 1
        except Exception:
            pass
    for layer, count in sorted(layer_count.items(), key=lambda x: -x[1])[:10]:
        print(f"    Layer '{layer}': {count} entities")

print("\n=== All block definitions ===")
for block in doc.blocks:
    ents = list(block)
    if ents:
        print(f"  Block '{block.name}': {len(ents)} entities")
        layer_count = defaultdict(int)
        for e in ents:
            try:
                layer_count[e.dxf.layer] += 1
            except Exception:
                pass
        for layer, count in sorted(layer_count.items(), key=lambda x: -x[1])[:5]:
            print(f"    Layer '{layer}': {count} entities")

# Try to get entities from the first non-empty layout
print("\n=== Scanning all entities for LINE/LWPOLYLINE ===")
all_line_lengths = defaultdict(list)   # layer -> [lengths]
all_poly_areas   = defaultdict(list)   # layer -> [areas]

for layout in doc.layouts:
    for e in layout:
        try:
            etype = e.dxftype()
            layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
            if etype == "LINE":
                s = (e.dxf.start.x, e.dxf.start.y)
                end = (e.dxf.end.x, e.dxf.end.y)
                L = math.sqrt((end[0]-s[0])**2 + (end[1]-s[1])**2)
                if L > 0:
                    all_line_lengths[layer].append(L)
            elif etype == "LWPOLYLINE":
                pts = list(e.get_points("xy"))
                if e.closed and len(pts) >= 3:
                    n = len(pts)
                    area = abs(sum(pts[i][0]*pts[(i+1)%n][1]-pts[(i+1)%n][0]*pts[i][1] for i in range(n)))/2
                    if area > 0:
                        all_poly_areas[layer].append(area)
        except Exception:
            pass

print(f"\nLayers with LINE entities:")
for layer, lengths in sorted(all_line_lengths.items(), key=lambda x: -sum(x[1])):
    total = sum(lengths)
    print(f"  '{layer}': {len(lengths)} lines, total length={total:.1f} units")

print(f"\nLayers with closed LWPOLYLINE (rooms):")
for layer, areas in sorted(all_poly_areas.items(), key=lambda x: -sum(x[1])):
    total = sum(areas)
    print(f"  '{layer}': {len(areas)} polygons, total area={total:.1f} sq units")

print(f"\n$INSUNITS = {doc.header.get('$INSUNITS')}  (6=meters, 4=mm, 1=inch)")
