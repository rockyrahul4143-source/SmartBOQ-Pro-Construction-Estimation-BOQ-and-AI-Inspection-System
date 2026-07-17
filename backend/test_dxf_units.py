import sys
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"
with open(DXF, "rb") as f:
    raw = f.read()

text = raw.decode("cp1252", errors="replace")
lines = text.splitlines()

# Check INSUNITS and coordinates
import math

# Find header
for i, l in enumerate(lines):
    if "$INSUNITS" in l and i+2 < len(lines):
        print(f"$INSUNITS = {lines[i+2].strip()}")

# Get first 10 LINE lengths (raw, no scaling)
entities_start = next((i for i, l in enumerate(lines) if l.strip() == "ENTITIES"), 0)
print(f"\nFirst 10 LINE lengths (raw drawing units):")
count = 0
i = entities_start
n = len(lines)
while i < n-1 and count < 10:
    if lines[i].strip() == "0" and i+1 < n and lines[i+1].strip() == "LINE":
        coords = {}
        j = i+2
        while j < n-1:
            c = lines[j].strip()
            v = lines[j+1].strip()
            if c == "0": break
            if c in ("10","20","11","21"):
                try: coords[c] = float(v)
                except: pass
            j += 2
        try:
            L = math.sqrt((coords["11"]-coords["10"])**2 + (coords["21"]-coords["20"])**2)
            print(f"  Line: ({coords['10']:.2f},{coords['20']:.2f}) -> ({coords['11']:.2f},{coords['21']:.2f}) = {L:.3f} units")
            count += 1
        except: pass
    i += 2

# Show LWPOLYLINE details
print(f"\nLWPOLYLINE details (flags, vertex count, area):")
i = entities_start
count = 0
while i < n-1 and count < 21:
    if lines[i].strip() == "0" and i+1 < n and lines[i+1].strip() == "LWPOLYLINE":
        pts = []; flags = 0; cur_x = None
        j = i+2
        while j < n-1:
            c = lines[j].strip(); v = lines[j+1].strip()
            if c == "0": break
            if c == "70":
                try: flags = int(v)
                except: pass
            elif c == "10":
                try: cur_x = float(v)
                except: cur_x = None
            elif c == "20" and cur_x is not None:
                try: pts.append((cur_x, float(v))); cur_x = None
                except: pass
            j += 2
        if pts:
            n_pts = len(pts)
            area = 0
            if n_pts >= 3:
                area = abs(sum(pts[k][0]*pts[(k+1)%n_pts][1]-pts[(k+1)%n_pts][0]*pts[k][1] for k in range(n_pts)))/2
            print(f"  LWPOLY: flags={flags} ({bin(flags)}), pts={n_pts}, area={area:.3f}, closed={bool(flags&1)}")
        count += 1
    i += 2
