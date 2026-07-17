"""
Backend server — Python 3.12 (QGIS) with TensorFlow support.
Auto-detects and loads AI models from ml_models/.
"""
import sys, os, site

# ── Fix: Add Python 3.14 DLLs to PATH so _sqlite3.pyd loads correctly ──
# QGIS Python 3.12 is missing _sqlite3.dll — use Python 3.14's version
PY14_DLLS = r"C:\Python314\DLLs"
if os.path.exists(PY14_DLLS):
    os.environ["PATH"] = PY14_DLLS + os.pathsep + os.environ.get("PATH", "")

PY14_LOCAL_DLLS = r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\DLLs"
if os.path.exists(PY14_LOCAL_DLLS):
    os.environ["PATH"] = PY14_LOCAL_DLLS + os.pathsep + os.environ.get("PATH", "")

# ── Add Python 3.12 user packages (pip install --user) ─
USER_SITE = site.getusersitepackages()
if USER_SITE and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

# ── QGIS Python 3.12 site-packages — EXCLUDED ──────────
# QGIS PIL/_imaging.dll is broken. We use user-installed packages only.
# QGIS_SITE = r"C:\Program Files\QGIS 3.44.11\apps\Python312\Lib\site-packages"

# ── REMOVE only QGIS site-packages (not QGIS stdlib) ────
# QGIS PIL/_imaging.dll crashes. Strip only the site-packages path.
QGIS_BAD = r"C:\Program Files\QGIS 3.44.11\apps\Python312\Lib\site-packages"
sys.path = [p for p in sys.path if p != QGIS_BAD]
# Re-add user site at front
if USER_SITE and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

# ── Python 3.14 packages (fastapi, sqlalchemy etc.) ────
PY14_SITE = r"C:\Users\acer\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages"
if os.path.exists(PY14_SITE) and PY14_SITE not in sys.path:
    sys.path.append(PY14_SITE)

# ── Environment ─────────────────────────────────────────
os.environ["DATABASE_URL"]    = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]      = "local-dev-secret-key-smartboq-pro-2024"
os.environ["ALLOWED_ORIGINS"] = "*"

# ── TensorFlow status ────────────────────────────────────
try:
    import tensorflow as tf
    print(f"  TensorFlow {tf.__version__} loaded — AI inspection ENABLED")
except ImportError:
    print("  TensorFlow not found — AI inspection will show model_not_loaded")
    print("  Install with: pip install tensorflow --user")

# ── Model status ─────────────────────────────────────────
import pathlib
ML_DIR = pathlib.Path(__file__).parent / "ml_models"
model_files = {
    "Concrete Crack (ResNet50)":    "ResNet50_model.h5",
    "Concrete Crack (VGG16)":       "VGG16_model.h5",
    "Concrete Crack (InceptionV3)": "InceptionV3_model.h5",
    "Pothole (MobileNetV2)":        "crack_model.h5",
}
print("\n  AI Model files:")
for name, fname in model_files.items():
    path = ML_DIR / fname
    if path.exists():
        size = round(path.stat().st_size / 1_048_576, 1)
        print(f"  [OK]  {fname} ({size} MB)")
    else:
        print(f"  [--]  {fname} NOT FOUND")

if __name__ == "__main__":
    import uvicorn
    print("\n  SmartBOQ Pro API: http://localhost:8000")
    print("  Docs:             http://localhost:8000/docs\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
