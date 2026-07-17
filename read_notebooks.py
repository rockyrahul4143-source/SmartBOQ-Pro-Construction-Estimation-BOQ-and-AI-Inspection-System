import json

for nb_file in ["1 .ipynb", "2.ipynb"]:
    print(f"\n{'='*60}")
    print(f"NOTEBOOK: {nb_file}")
    print('='*60)
    try:
        with open(nb_file, encoding="utf-8") as f:
            nb = json.load(f)
        cells = nb.get("cells", [])
        for i, cell in enumerate(cells):
            src = "".join(cell.get("source", []))
            if src.strip():
                print(f"\n--- Cell {i+1} ({cell['cell_type']}) ---")
                print(src[:2000])
                # Also show outputs
                for out in cell.get("outputs", []):
                    txt = "".join(out.get("text", out.get("data", {}).get("text/plain", [])))
                    if txt.strip():
                        print(f"  OUTPUT: {txt[:500]}")
    except Exception as e:
        print(f"Error reading {nb_file}: {e}")
