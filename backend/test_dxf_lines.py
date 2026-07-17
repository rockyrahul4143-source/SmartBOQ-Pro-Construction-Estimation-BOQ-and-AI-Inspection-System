"""Check exact format of lines in ENTITIES section."""
import sys
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"
with open(DXF, "rb") as f:
    raw = f.read()

text = raw.decode("cp1252", errors="replace")
lines = text.splitlines()

# Find ENTITIES section
start = None
for i, l in enumerate(lines):
    if l.strip() == "ENTITIES":
        start = i
        break

if start:
    print(f"ENTITIES starts at line {start}")
    print("First 20 lines (repr):")
    for i, l in enumerate(lines[start:start+25]):
        print(f"  [{start+i}] raw={repr(l)}, stripped={repr(l.strip())}")
