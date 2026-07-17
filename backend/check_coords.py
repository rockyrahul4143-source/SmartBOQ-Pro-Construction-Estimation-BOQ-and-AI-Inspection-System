import sys, math
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"
raw = open(DXF, "rb").read()
text = raw.decode("cp1252", errors="replace")
all_lines = text.splitlines()

# Find ENTITIES section start
ent_start = 0
for idx, l in enumerate(all_lines):
    if l.strip() == "ENTITIES":
        ent_start = idx
        break

# Find ENDSEC after ENTITIES
ent_end = len(all_lines)
for idx in range(ent_start + 1, len(all_lines)):
    if all_lines[idx].strip() == "ENDSEC":
        ent_end = idx
        break

lines = all_lines[ent_start:ent_end]
print(f"ENTITIES section: {len(lines)} lines (raw[{ent_start}:{ent_end}])")
print(f"INSUNITS=5 means: centimetres")
print()

# Parse using CORRECT step: lines[i] = code, lines[i+1] = value
# BUT ENTITIES header is 1 line, then starts "  0\nLINE"
# So the first pair is lines[0]="ENTITIES", lines[1]="  0" — misaligned
# We need to start from the "  0" that precedes "LINE"

# Count all entity types
entity_counts = {}
line_lengths = []
poly_info = []

i = 0
n = len(lines)
while i < n:
    stripped = lines[i].strip()
    # A group code is a short numeric string
    # A value follows on the NEXT line
    if stripped == "0" and i+1 < n:
        etype = lines[i+1].strip().upper()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

        if etype == "LINE":
            coords = {}
            j = i + 2
            while j < n:
                c = lines[j].strip()
                if c == "0":
                    break
                if j+1 < n:
                    v = lines[j+1].strip()
                    if c in ("10","20","11","21"):
                        try:
                            coords[c] = float(v)
                        except ValueError:
                            pass
                j += 2
            if all(k in coords for k in ("10","20","11","21")):
                L = math.sqrt((coords["11"]-coords["10"])**2 + (coords["21"]-coords["20"])**2)
                if L > 0:
                    line_lengths.append(L)

        elif etype == "LWPOLYLINE":
            pts = []
            flags = 0
            cur_x = None
            j = i + 2
            while j < n:
                c = lines[j].strip()
                if c == "0":
                    break
                if j+1 < n:
                    v = lines[j+1].strip()
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
            poly_info.append({"pts": len(pts), "flags": flags, "closed": bool(flags & 1)})

    i += 1   # step by 1, not 2 — let the "0" detection handle alignment

print(f"Entity counts: {entity_counts}")
print(f"\nFirst 10 LINE lengths (raw units):")
for L in line_lengths[:10]:
    print(f"  {L:.4f}")
print(f"Total line lengths (raw): {sum(line_lengths):.2f}")
print(f"Min: {min(line_lengths):.4f}, Max: {max(line_lengths):.4f}")
print()
print(f"INSUNITS=5 (cm) → scale=0.01 → wall length = {sum(line_lengths)*0.01:.2f} m")
print()
print(f"LWPOLYLINE details:")
for p in poly_info:
    print(f"  pts={p['pts']}, flags={p['flags']}, closed={p['closed']}")
