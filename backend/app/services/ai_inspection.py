"""
AI Visual Inspection Service
================================
Uses ONNX Runtime instead of TensorFlow.
- onnxruntime: ~6MB (vs TensorFlow 400MB+)
- Works on Render free tier (512MB RAM)
- Models downloaded from GitHub Releases at startup

Models:
  resnet50_crack    -> ResNet50_model.onnx    (120x120)
  vgg16_crack       -> VGG16_model.onnx       (120x120)
  inceptionv3_crack -> InceptionV3_model.onnx (150x150)
  mobilenetv2_road  -> crack_model.onnx       (160x160)

Currency: INR (Indian Rupees)
"""
from __future__ import annotations
import os, io, hashlib, logging, urllib.request, time
from pathlib import Path
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Model directory ───────────────────────────────────
_IS_RENDER = os.getenv("APP_ENV") == "production" or os.getenv("RENDER") == "true"
ML_DIR = Path("/tmp/ml_models") if _IS_RENDER else Path(__file__).parent.parent.parent / "ml_models"
ML_DIR.mkdir(parents=True, exist_ok=True)

# GitHub Releases — ONNX models (public, no auth)
_GH = (
    "https://github.com/rockyrahul4143-source/"
    "SmartBOQ-Pro-Construction-Estimation-BOQ-and-AI-Inspection-System/"
    "releases/download/ml-models-v2-onnx"
)
MODEL_URLS = {
    "ResNet50_model.onnx":    f"{_GH}/ResNet50_model.onnx",
    "VGG16_model.onnx":       f"{_GH}/VGG16_model.onnx",
    "InceptionV3_model.onnx": f"{_GH}/InceptionV3_model.onnx",
    "crack_model.onnx":       f"{_GH}/crack_model.onnx",
}

# ── Session cache ─────────────────────────────────────
_sessions: dict = {}
ONNX_AVAILABLE: bool = False
TF_AVAILABLE: bool = False  # kept for API compat


# ── Download with retry ───────────────────────────────
def _download(fname: str) -> bool:
    dest = ML_DIR / fname
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return True
    url = MODEL_URLS.get(fname)
    if not url:
        logger.error(f"No URL for {fname}")
        return False
    for attempt in range(1, 4):
        logger.info(f"Downloading {fname} (attempt {attempt}/3)...")
        try:
            if dest.exists():
                dest.unlink()
            urllib.request.urlretrieve(url, str(dest))
            mb = dest.stat().st_size / 1_048_576
            if mb < 1.0:
                raise ValueError(f"Too small: {mb:.1f}MB")
            logger.info(f"Downloaded {fname} ({mb:.1f}MB) ✓")
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            if dest.exists():
                dest.unlink()
            if attempt < 3:
                time.sleep(3)
    logger.error(f"All attempts failed for {fname}")
    return False


# ── Load ONNX session ─────────────────────────────────
def _load(key: str, onnx_name: str):
    global ONNX_AVAILABLE
    if key in _sessions:
        return _sessions[key]
    path = ML_DIR / onnx_name
    # Try local .onnx first, then download
    if not path.exists() and _IS_RENDER:
        _download(onnx_name)
    # Fallback: try local .h5 → already converted locally
    if not path.exists():
        h5_path = ML_DIR / onnx_name.replace(".onnx", ".h5")
        if not h5_path.exists():
            logger.warning(f"Not found: {path}")
            return None
        logger.warning(f"ONNX not found, h5 present but TF not available on Render")
        return None
    try:
        import onnxruntime as ort
        ONNX_AVAILABLE = True
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
        _sessions[key] = sess
        logger.info(f"Loaded [{key}] from {onnx_name}")
        return sess
    except Exception as e:
        logger.error(f"Failed to load {key}: {e}")
        return None


# ── Startup preload ───────────────────────────────────
def preload_all_models() -> None:
    """Called at server startup. Downloads models in a background thread so startup is fast."""
    global ONNX_AVAILABLE, TF_AVAILABLE
    try:
        import onnxruntime
        ONNX_AVAILABLE = True
        TF_AVAILABLE   = True
        logger.info(f"ONNX Runtime {onnxruntime.__version__} ready")
    except ImportError:
        logger.warning("onnxruntime not installed — AI inspection disabled")
        return

    if _IS_RENDER:
        # Download in background thread so server starts immediately
        import threading
        def _bg():
            logger.info("Background: downloading ONNX models...")
            for fname in MODEL_URLS:
                _download(fname)
            for key, onnx_name in [
                ("resnet50_crack",    "ResNet50_model.onnx"),
                ("vgg16_crack",       "VGG16_model.onnx"),
                ("inceptionv3_crack", "InceptionV3_model.onnx"),
                ("mobilenetv2_road",  "crack_model.onnx"),
            ]:
                _load(key, onnx_name)
            loaded = len(_sessions)
            logger.info(f"Background: preloaded {loaded}/4 models")
        threading.Thread(target=_bg, daemon=True).start()
    else:
        # Local: load synchronously (files already present)
        for key, onnx_name in [
            ("resnet50_crack",    "ResNet50_model.onnx"),
            ("vgg16_crack",       "VGG16_model.onnx"),
            ("inceptionv3_crack", "InceptionV3_model.onnx"),
            ("mobilenetv2_road",  "crack_model.onnx"),
        ]:
            _load(key, onnx_name)
        logger.info(f"Preloaded {len(_sessions)}/4 models")


def ensure_models_loaded() -> bool:
    """Called before each inspection — lazy load if startup download was missed."""
    global ONNX_AVAILABLE, TF_AVAILABLE
    if ONNX_AVAILABLE and len(_sessions) >= 3:
        return True
    try:
        import onnxruntime
        ONNX_AVAILABLE = True
        TF_AVAILABLE   = True
    except ImportError:
        return False
    for fname in MODEL_URLS:
        _download(fname)
    for key, onnx_name in [
        ("resnet50_crack",    "ResNet50_model.onnx"),
        ("vgg16_crack",       "VGG16_model.onnx"),
        ("inceptionv3_crack", "InceptionV3_model.onnx"),
        ("mobilenetv2_road",  "crack_model.onnx"),
    ]:
        if key not in _sessions:
            _load(key, onnx_name)
    return len(_sessions) > 0


# ── Preprocessing ─────────────────────────────────────
def _preprocess(image_bytes: bytes, size: tuple) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(size)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


def _predict(sess, img_arr: np.ndarray) -> float:
    inp_name = sess.get_inputs()[0].name
    result   = sess.run(None, {inp_name: img_arr})
    return float(result[0][0][0])


# ── Severity ──────────────────────────────────────────
def _severity(prob: float, detected: bool):
    if not detected:
        return "none", 0.0
    s = prob * 100
    if s < 60:  return "low",      s
    if s < 75:  return "moderate", s
    if s < 90:  return "high",     s
    return "critical", s


# ── Repair cost (INR, CPWD DSR 2024) ─────────────────
def _repair_cost_inr(itype: str, confidence: float, detected: bool):
    if not detected or confidence < 0.5:
        return 0, 0
    s = confidence * 100
    if itype in ("concrete_crack", "surface_crack"):
        if s < 60:   return 3_000,    12_000
        elif s < 70: return 10_000,   35_000
        elif s < 80: return 30_000,   90_000
        elif s < 90: return 80_000,   2_50_000
        else:        return 2_50_000, 10_00_000
    elif itype == "road_damage":
        if s < 60:   return 4_000,    15_000
        elif s < 70: return 15_000,   50_000
        elif s < 80: return 60_000,   2_00_000
        elif s < 90: return 1_80_000, 6_00_000
        else:        return 5_00_000, 20_00_000
    else:
        if s < 60:   return 5_000,    25_000
        elif s < 75: return 25_000,   1_00_000
        elif s < 90: return 1_00_000, 4_00_000
        else:        return 4_00_000, 15_00_000


# ── Recommendations ───────────────────────────────────
_RECS = {
    "concrete_crack": {
        "low":      ("Hairline cracks detected. Apply epoxy sealant. Monitor monthly.", "soon"),
        "moderate": ("Visible cracks. Epoxy injection recommended. Structural assessment advised.", "soon"),
        "high":     ("Significant structural cracks. Immediate engineer inspection required.", "immediate"),
        "critical": ("CRITICAL: Major structural failure risk. Stop use. Emergency intervention required.", "immediate"),
    },
    "road_damage": {
        "low":      ("Minor surface wear. Cold mix patching recommended.", "soon"),
        "moderate": ("Pothole detected. Hot mix patching required.", "soon"),
        "high":     ("Severe potholes. Immediate patching required. Risk of vehicle damage.", "immediate"),
        "critical": ("Dangerous road condition. Close section. Full resurfacing required.", "immediate"),
    },
}

def _recommendation(itype: str, severity: str, detected: bool):
    if not detected or severity == "none":
        return "No defects detected. Routine inspection recommended in 6 months.", "monitor"
    text, urgency = _RECS.get(itype, {}).get(severity, ("Defect detected. Professional assessment required.", "soon"))
    return text, urgency


# ── Not-loaded fallback ───────────────────────────────
def _not_loaded(itype: str, filename: str, classes: list) -> dict:
    return {
        "inspection_type": itype,
        "model_name":      "NOT LOADED",
        "status":          "model_weights_not_found",
        "message":         f"Place '{filename}' in backend/ml_models/ to enable AI inspection.",
        "classes":         classes,
        "severity":        "none",
        "severity_score":  0.0,
        "confidence":      0.0,
        "mock_prediction": {"predicted_class": classes[0], "confidence": 0.0},
    }


# ══════════════════════════════════════════════════════
# PUBLIC INSPECTION FUNCTIONS
# ══════════════════════════════════════════════════════

def inspect_concrete_crack(image_bytes: bytes) -> dict:
    ensure_models_loaded()
    specs = [
        ("resnet50_crack",    "ResNet50_model.onnx",    (120, 120)),
        ("vgg16_crack",       "VGG16_model.onnx",       (120, 120)),
        ("inceptionv3_crack", "InceptionV3_model.onnx", (150, 150)),
    ]
    preds, names = [], []
    for key, onnx_name, size in specs:
        sess = _load(key, onnx_name)
        if sess:
            prob = _predict(sess, _preprocess(image_bytes, size))
            preds.append(prob)
            names.append(key.split("_")[0].upper())

    if not preds:
        return _not_loaded("concrete_crack",
                           "ResNet50_model.onnx / VGG16_model.onnx / InceptionV3_model.onnx",
                           ["No Crack", "Crack Detected"])

    avg  = float(np.mean(preds))
    det  = avg > 0.5
    sev, score = _severity(avg, det)
    rec, urg   = _recommendation("concrete_crack", sev, det)
    cmin, cmax = _repair_cost_inr("concrete_crack", avg, det)

    return {
        "inspection_type":           "concrete_crack",
        "model_name":                f"Ensemble ONNX ({', '.join(names)})",
        "predicted_class":           "Crack Detected" if det else "No Crack",
        "confidence":                round(avg, 4),
        "severity":                  sev,
        "severity_score":            round(score, 1),
        "recommendation":            rec,
        "repair_urgency":            urg,
        "estimated_repair_cost_min": cmin,
        "estimated_repair_cost_max": cmax,
        "currency":                  "INR",
        "class_probabilities": {
            "No Crack":       round(1 - avg, 4),
            "Crack Detected": round(avg, 4),
        },
        "individual_predictions": [round(p, 4) for p in preds],
    }


def inspect_surface_crack_ensemble(image_bytes: bytes) -> dict:
    r = inspect_concrete_crack(image_bytes)
    r["inspection_type"] = "surface_crack"
    return r


def inspect_road_damage(image_bytes: bytes) -> dict:
    ensure_models_loaded()
    sess = _load("mobilenetv2_road", "crack_model.onnx")
    if sess is None:
        return _not_loaded("road_damage", "crack_model.onnx",
                           ["NEGATIVE (Clean Road)", "POSITIVE (Pothole)"])

    prob = _predict(sess, _preprocess(image_bytes, (160, 160)))
    det  = prob > 0.5
    sev, score = _severity(prob, det)
    if det and sev == "low":
        sev = "moderate"
    rec, urg   = _recommendation("road_damage", sev, det)
    cmin, cmax = _repair_cost_inr("road_damage", prob, det)

    return {
        "inspection_type":           "road_damage",
        "model_name":                "MobileNetV2 ONNX (crack_model.onnx)",
        "predicted_class":           "POSITIVE (Pothole)" if det else "NEGATIVE (Clean Road)",
        "confidence":                round(prob, 4),
        "severity":                  sev,
        "severity_score":            round(score, 1),
        "detections":                [{"class": "pothole", "confidence": round(prob, 4)}] if det else [],
        "total_defects":             1 if det else 0,
        "recommendation":            rec,
        "repair_urgency":            urg,
        "estimated_repair_cost_min": cmin,
        "estimated_repair_cost_max": cmax,
        "currency":                  "INR",
        "class_probabilities": {
            "NEGATIVE (Clean Road)": round(1 - prob, 4),
            "POSITIVE (Pothole)":    round(prob, 4),
        },
    }


def inspect_building_safety(image_bytes: bytes) -> dict:
    return _not_loaded(
        "building_safety", "efficientnetb7_safety.onnx",
        ["Safe", "Minor Damage", "Moderate Damage", "Severe Damage"],
    )


# ── Save uploaded image ───────────────────────────────
def save_inspection_image(image_bytes: bytes, itype: str, filename: str, upload_dir: str) -> str:
    save_dir = os.path.join(upload_dir, "inspections")
    os.makedirs(save_dir, exist_ok=True)
    h    = hashlib.md5(image_bytes).hexdigest()[:8]
    path = os.path.join(save_dir, f"{itype}_{h}_{filename}")
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path
