"""
AI Visual Inspection Service
================================
Models (consistent cache keys used everywhere):
  resnet50_crack    -> ResNet50_model.h5    (120x120)
  vgg16_crack       -> VGG16_model.h5       (120x120)
  inceptionv3_crack -> InceptionV3_model.h5 (150x150)
  mobilenetv2_road  -> crack_model.h5       (160x160)

Currency: INR (Indian Rupees)
Repair costs: dynamic — based on actual confidence score, no hard limits

Model hosting: GitHub Releases (public, permanent, no auth needed)
"""
from __future__ import annotations
import os, io, hashlib, logging, urllib.request
from pathlib import Path
from typing import Optional
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Model directory ───────────────────────────────────
# On Render: /tmp/ml_models (ephemeral — downloaded at every startup)
# Locally:   backend/ml_models (persistent — already present)
_IS_RENDER = os.getenv("APP_ENV") == "production" or os.getenv("RENDER") == "true"
if _IS_RENDER:
    ML_DIR = Path("/tmp/ml_models")
else:
    ML_DIR = Path(__file__).parent.parent.parent / "ml_models"

ML_DIR.mkdir(parents=True, exist_ok=True)

# GitHub Release download URLs — public, no auth, permanent
_GH_BASE = (
    "https://github.com/rockyrahul4143-source/"
    "SmartBOQ-Pro-Construction-Estimation-BOQ-and-AI-Inspection-System/"
    "releases/download/ml-models-v1"
)
MODEL_URLS = {
    "ResNet50_model.h5":    f"{_GH_BASE}/ResNet50_model.h5",
    "VGG16_model.h5":       f"{_GH_BASE}/VGG16_model.h5",
    "InceptionV3_model.h5": f"{_GH_BASE}/InceptionV3_model.h5",
    "crack_model.h5":       f"{_GH_BASE}/crack_model.h5",
}

# ── Model cache ───────────────────────────────────────
_models: dict = {}
TF_AVAILABLE: bool = False


# ── Download a single model file ─────────────────────
def _download_model(fname: str) -> bool:
    dest = ML_DIR / fname
    if dest.exists():
        return True
    url = MODEL_URLS.get(fname)
    if not url:
        return False
    logger.info(f"Downloading {fname} from GitHub Releases...")
    try:
        urllib.request.urlretrieve(url, str(dest))
        size_mb = dest.stat().st_size / 1_048_576
        logger.info(f"Downloaded {fname} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        logger.error(f"Failed to download {fname}: {e}")
        if dest.exists():
            dest.unlink()
        return False

# ── Model cache ───────────────────────────────────────
_models: dict = {}
TF_AVAILABLE: bool = False


# ── Load one Keras model ──────────────────────────────
def _load_model(key: str, h5_path: Path):
    global TF_AVAILABLE
    if key in _models:
        return _models[key]
    # Download from GitHub Releases if not present
    if not h5_path.exists() and _IS_RENDER:
        _download_model(h5_path.name)
    if not h5_path.exists():
        logger.warning(f"Not found: {h5_path}")
        return None
    try:
        import tensorflow as tf
        TF_AVAILABLE = True
        model = tf.keras.models.load_model(str(h5_path))
        _models[key] = model
        logger.info(f"Loaded [{key}] from {h5_path.name}")
        return model
    except Exception as e:
        logger.error(f"Failed [{key}]: {e}")
        return None


# ── Startup preload ───────────────────────────────────
def preload_all_models() -> None:
    global TF_AVAILABLE
    try:
        import tensorflow as tf
        TF_AVAILABLE = True
        logger.info(f"TensorFlow {tf.__version__} ready")
    except ImportError:
        logger.warning("TensorFlow not available — AI inspection disabled")
        return

    # On Render: download all models upfront before loading
    if _IS_RENDER:
        logger.info("Render environment detected — downloading model files...")
        for fname in MODEL_URLS:
            _download_model(fname)

    specs = [
        ("resnet50_crack",    ML_DIR / "ResNet50_model.h5"),
        ("vgg16_crack",       ML_DIR / "VGG16_model.h5"),
        ("inceptionv3_crack", ML_DIR / "InceptionV3_model.h5"),
        ("mobilenetv2_road",  ML_DIR / "crack_model.h5"),
    ]
    for key, path in specs:
        _load_model(key, path)
    logger.info(f"Preloaded {len(_models)}/4 models")


# ── Image preprocessing ───────────────────────────────
def _preprocess(image_bytes: bytes, size: tuple) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(size)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


# ── Severity from probability ─────────────────────────
def _severity(prob: float, detected: bool):
    if not detected:
        return "none", 0.0
    s = prob * 100
    if s < 60:  return "low",      s
    if s < 75:  return "moderate", s
    if s < 90:  return "high",     s
    return "critical", s


# ── Dynamic repair cost (INR) — scales with confidence ─
# No fixed limits. Cost reflects actual damage probability.
# Sources: CPWD DSR 2024, MoRTH schedule, Delhi PWD 2024
def _repair_cost_inr(itype: str, confidence: float, detected: bool):
    if not detected or confidence < 0.5:
        return 0, 0

    s = confidence * 100  # percentage

    if itype in ("concrete_crack", "surface_crack"):
        # Epoxy injection ₹200-800/m, polymer mortar ₹1200/m², structural ₹2500/m²
        if s < 55:   return 1_000,    6_000       # very early hairline
        elif s < 60: return 3_000,    12_000      # hairline crack — sealant
        elif s < 65: return 6_000,    20_000      # fine crack — epoxy primer
        elif s < 70: return 10_000,   35_000      # visible crack — epoxy injection
        elif s < 75: return 18_000,   55_000      # moderate — polymer mortar
        elif s < 80: return 30_000,   90_000      # structural crack — repair mortar
        elif s < 85: return 50_000,   1_50_000    # serious — engineer + repair
        elif s < 90: return 80_000,   2_50_000    # major — structural work
        elif s < 95: return 1_50_000, 4_50_000    # critical — full intervention
        else:        return 2_50_000, 10_00_000   # severe — rebuild section

    elif itype == "road_damage":
        # Cold mix ₹180/m², hot mix ₹350/m², milling+resurfacing ₹800/m²
        if s < 55:   return 1_500,    8_000
        elif s < 60: return 4_000,    15_000      # minor surface wear
        elif s < 65: return 8_000,    28_000      # early pothole — cold mix
        elif s < 70: return 15_000,   50_000      # pothole — hot mix patch
        elif s < 75: return 30_000,   90_000      # multiple potholes
        elif s < 80: return 60_000,   2_00_000    # large pothole area
        elif s < 85: return 1_00_000, 3_50_000    # extensive damage
        elif s < 90: return 1_80_000, 6_00_000    # milling required
        elif s < 95: return 3_00_000, 10_00_000   # resurfacing needed
        else:        return 5_00_000, 20_00_000   # full reconstruction

    else:
        # Building safety — general
        if s < 60:   return 5_000,   25_000
        elif s < 75: return 25_000,  1_00_000
        elif s < 90: return 1_00_000, 4_00_000
        else:        return 4_00_000, 15_00_000


# ── Recommendations ───────────────────────────────────
_RECS = {
    "concrete_crack": {
        "low":      ("Hairline cracks detected. Apply epoxy sealant or crack filler. Monitor monthly.", "soon"),
        "moderate": ("Visible cracks found. Epoxy injection recommended. Structural assessment advised.", "soon"),
        "high":     ("Significant structural cracks. Immediate engineer inspection required. Apply polymer mortar.", "immediate"),
        "critical": ("CRITICAL: Major structural failure risk. Stop use. Emergency structural intervention required.", "immediate"),
    },
    "road_damage": {
        "low":      ("Minor surface wear. Cold mix patching recommended. Schedule in routine maintenance.", "soon"),
        "moderate": ("Pothole detected. Hot mix patching required. Mark for traffic safety.", "soon"),
        "high":     ("Severe potholes. Immediate hot mix patching. Risk of vehicle damage and accidents.", "immediate"),
        "critical": ("Dangerous road condition. Close section immediately. Full milling and resurfacing required.", "immediate"),
    },
}

def _recommendation(itype: str, severity: str, detected: bool):
    if not detected or severity == "none":
        return "No defects detected. Routine inspection recommended in 6 months.", "monitor"
    text, urgency = _RECS.get(itype, {}).get(
        severity, ("Defect detected. Professional assessment required.", "soon")
    )
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
    """Ensemble: ResNet50 + VGG16 + InceptionV3."""
    specs = [
        ("resnet50_crack",    ML_DIR / "ResNet50_model.h5",    (120, 120)),
        ("vgg16_crack",       ML_DIR / "VGG16_model.h5",       (120, 120)),
        ("inceptionv3_crack", ML_DIR / "InceptionV3_model.h5", (150, 150)),
    ]
    preds, names = [], []
    for key, path, size in specs:
        m = _load_model(key, path)
        if m:
            prob = float(m.predict(_preprocess(image_bytes, size), verbose=0)[0][0])
            preds.append(prob)
            names.append(key.split("_")[0].upper())

    if not preds:
        return _not_loaded("concrete_crack",
                           "ResNet50_model.h5 / VGG16_model.h5 / InceptionV3_model.h5",
                           ["No Crack", "Crack Detected"])

    avg  = float(np.mean(preds))
    det  = avg > 0.5
    sev, score = _severity(avg, det)
    rec, urg   = _recommendation("concrete_crack", sev, det)
    cmin, cmax = _repair_cost_inr("concrete_crack", avg, det)

    return {
        "inspection_type":            "concrete_crack",
        "model_name":                 f"Ensemble ({', '.join(names)})",
        "predicted_class":            "Crack Detected" if det else "No Crack",
        "confidence":                 round(avg, 4),
        "severity":                   sev,
        "severity_score":             round(score, 1),
        "recommendation":             rec,
        "repair_urgency":             urg,
        "estimated_repair_cost_min":  cmin,
        "estimated_repair_cost_max":  cmax,
        "currency":                   "INR",
        "class_probabilities": {
            "No Crack":       round(1 - avg, 4),
            "Crack Detected": round(avg, 4),
        },
        "individual_predictions": [round(p, 4) for p in preds],
    }


def inspect_surface_crack_ensemble(image_bytes: bytes) -> dict:
    """Same ensemble as concrete crack."""
    r = inspect_concrete_crack(image_bytes)
    r["inspection_type"] = "surface_crack"
    return r


def inspect_road_damage(image_bytes: bytes) -> dict:
    """MobileNetV2 pothole detector — crack_model.h5."""
    m = _load_model("mobilenetv2_road", ML_DIR / "crack_model.h5")
    if m is None:
        return _not_loaded("road_damage", "crack_model.h5",
                           ["NEGATIVE (Clean Road)", "POSITIVE (Pothole)"])

    prob = float(m.predict(_preprocess(image_bytes, (160, 160)), verbose=0)[0][0])
    det  = prob > 0.5
    sev, score = _severity(prob, det)
    if det and sev == "low":
        sev = "moderate"  # potholes always at least moderate
    rec, urg   = _recommendation("road_damage", sev, det)
    cmin, cmax = _repair_cost_inr("road_damage", prob, det)

    return {
        "inspection_type":            "road_damage",
        "model_name":                 "MobileNetV2 (crack_model.h5)",
        "predicted_class":            "POSITIVE (Pothole)" if det else "NEGATIVE (Clean Road)",
        "confidence":                 round(prob, 4),
        "severity":                   sev,
        "severity_score":             round(score, 1),
        "detections":                 [{"class": "pothole", "confidence": round(prob, 4)}] if det else [],
        "total_defects":              1 if det else 0,
        "worst_defect":               "pothole" if det else "none",
        "recommendation":             rec,
        "repair_urgency":             urg,
        "estimated_repair_cost_min":  cmin,
        "estimated_repair_cost_max":  cmax,
        "currency":                   "INR",
        "class_probabilities": {
            "NEGATIVE (Clean Road)": round(1 - prob, 4),
            "POSITIVE (Pothole)":    round(prob, 4),
        },
    }


def inspect_building_safety(image_bytes: bytes) -> dict:
    """EfficientNetB7 — not yet trained."""
    return _not_loaded(
        "building_safety", "efficientnetb7_safety.h5",
        ["Safe", "Minor Damage", "Moderate Damage", "Severe Damage"],
    )


# ── Save uploaded image ───────────────────────────────
def save_inspection_image(image_bytes: bytes, itype: str,
                          filename: str, upload_dir: str) -> str:
    save_dir = os.path.join(upload_dir, "inspections")
    os.makedirs(save_dir, exist_ok=True)
    h = hashlib.md5(image_bytes).hexdigest()[:8]
    path = os.path.join(save_dir, f"{itype}_{h}_{filename}")
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path
