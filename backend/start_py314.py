"""
Backend startup using Python 3.14 (system Python).
TensorFlow AI models are loaded via QGIS Python 3.12 subprocess when needed.
Run: python start_py314.py
"""
import sys, os, pathlib

os.environ["DATABASE_URL"]    = "sqlite:///./smartboq.db"
os.environ["SECRET_KEY"]      = "local-dev-secret-key-smartboq-pro-2024"
os.environ["ALLOWED_ORIGINS"] = "*"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))

# ── Try loading TensorFlow via QGIS Python 3.12 ──────
QGIS_PY = r"C:\Program Files\QGIS 3.44.11\apps\Python312\python.exe"
TF_LOADER = BASE / "tf_loader_service.py"
os.environ["QGIS_PYTHON"] = QGIS_PY
os.environ["TF_LOADER"]   = str(TF_LOADER)

# ── Check if TF is available directly ────────────────
try:
    import tensorflow as tf
    print(f"  TensorFlow {tf.__version__} loaded directly — AI ENABLED")
    os.environ["TF_AVAILABLE"] = "1"
except ImportError:
    print("  TensorFlow not on Python 3.14 — AI uses QGIS Python 3.12 subprocess")
    os.environ["TF_AVAILABLE"] = "0"

# ── Print startup info ────────────────────────────────
ml_dir = BASE / "ml_models"
models = ["ResNet50_model.h5","VGG16_model.h5","InceptionV3_model.h5","crack_model.h5"]
print("  AI Model files:")
for m in models:
    path = ml_dir / m
    status = f"[OK]  {m} ({round(path.stat().st_size/1048576,1)} MB)" if path.exists() else f"[!!]  {m} NOT FOUND"
    print(f"  {status}")

print(f"  SmartBOQ Pro API: http://localhost:8000")
print(f"  Docs:             http://localhost:8000/docs")

# ── Start uvicorn ─────────────────────────────────────
import uvicorn
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8000,
    reload=False,
    log_level="info",
)
