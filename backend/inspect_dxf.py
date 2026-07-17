"""Diagnose the DXF file and find all layer names."""
import sys
sys.path.insert(0, r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")

DXF = r"C:\Users\acer\OneDrive\Desktop\Automated Quantity\smartboq-pro\2 bhk independent house plan.dxf"

with open(DXF, "rb") as f:
    raw = f.read()

text = raw.decode("cp1252", errors="replace")
lines = text.splitlines()
print(f"Total lines: {len(lines)}")
print(f"Lines 39120-39140:")
for i, l in enumerate(lines[39120:39140], 39121):
    print(f"  {i}: {repr(l[:100])}")

# Collect all unique layer names
layer_names = set()
for i, l in enumerate(lines):
    if l.strip() == "8" and i + 1 < len(lines):
        layer_names.add(lines[i + 1].strip())

print(f"\nTotal unique layers: {len(layer_names)}")
print("All layers:")
for name in sorted(layer_names):
    print(f"  '{name}'")
