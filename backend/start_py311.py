"""
SmartBOQ Pro Backend — Python 3.11 (Stable)
"""
import sys, os, pathlib, subprocess

# ── If user site-packages not disabled, re-launch with it disabled ────────
# This is the ONLY reliable way to prevent Python 3.12 packages bleeding in
if os.environ.get("SMARTBOQ_CLEAN_LAUNCH") != "1":
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"       # blocks AppData\Roaming\PythonXXX
    env["SMARTBOQ_CLEAN_LAUNCH"] = "1"
    result = subprocess.run(
        [sys.executable] + sys.argv,
        env=env
    )
    sys.exit(result.returncode)

# ── From here we run with PYTHONNOUSERSITE=1 ─────────────────────────────
# Add Python 3.11 site-packages explicitly (since user site is blocked)
PY311_SITE = r"C:\Users\acer\AppData\Local\Programs\Python\Python311\Lib\site-packages"
if PY311_SITE not in sys.path:
    sys.path.insert(1, PY311_SITE)

# Environment
os.environ.setdefault("DATABASE_URL",    "sqlite:///./smartboq.db")
os.environ.setdefault("SECRET_KEY",      "local-dev-secret-key-smartboq-pro-2024")
os.environ.setdefault("ALLOWED_ORIGINS", "*")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))

# Quick dependency check
print("\n  SmartBOQ Pro — Python 3.11 Backend")
print(f"  Python: {sys.version.split()[0]}")
missing = []
for pkg in ["fastapi", "sqlalchemy", "pydantic", "uvicorn", "jose", "passlib"]:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
        print(f"  !! MISSING: {pkg}")

if missing:
    print(f"\n  Run: python -m pip install {' '.join(missing)}")
    sys.exit(1)
print("  Core packages: OK")

# TensorFlow check — try Python 3.11 first, then QGIS Python 3.12
TF_OK = False
try:
    import tensorflow as tf
    print(f"  TensorFlow {tf.__version__}: OK (Python 3.11)")
    TF_OK = True
except ImportError:
    # Try adding QGIS Python 3.12 TF packages to path
    QGIS_SITE = r"C:\Users\acer\AppData\Roaming\Python\Python312\site-packages"
    import sys
    if QGIS_SITE not in sys.path:
        sys.path.insert(1, QGIS_SITE)
    try:
        import tensorflow as tf
        print(f"  TensorFlow {tf.__version__}: OK (via QGIS Python 3.12 packages)")
        TF_OK = True
    except ImportError:
        print("  TensorFlow: not installed (AI inspection disabled)")
        print("  To enable: pip install tensorflow")

# Model files
ML_DIR = BASE / "ml_models"
models = {"ResNet50_model.h5":"resnet50_crack","VGG16_model.h5":"vgg16_crack",
          "InceptionV3_model.h5":"inceptionv3_crack","crack_model.h5":"mobilenetv2_road"}
print("\n  AI Models:")
all_ok = True
for fname in models:
    p = ML_DIR / fname
    if p.exists():
        print(f"  [OK] {fname} ({round(p.stat().st_size/1048576,1)} MB)")
    else:
        print(f"  [--] {fname} NOT FOUND")
        all_ok = False

# Preload models
if TF_OK and all_ok:
    print("\n  Loading models into memory...")
    try:
        from app.services.ai_inspection import preload_all_models
        preload_all_models()
        print("  All models ready!")
    except Exception as e:
        print(f"  Model load warning: {e}")

print("\n  =========================================")
print("  API:  http://localhost:8000")
print("  Docs: http://localhost:8000/docs")
print("  =========================================\n")

import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
