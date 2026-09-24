"""
AI Visual Inspection Service — Memory-Optimised for Render Free Tier (512 MB)
=============================================================================
Key changes vs previous version:
- Only ONE model loaded per inspection (not all 4 at once)
- No background preload thread — models downloaded/loaded on first use
- Model eviction: only keeps the LAST used model in RAM (~90 MB max)
- Image bytes explicitly deleted after inference
- Total RAM for AI: ~90-100 MB (was ~300 MB)
"""
from __future__ import annotations
import os, io, gc, hashlib, logging, urllib.request, time
from pathlib import Path
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_IS_RENDER = os.getenv("APP_ENV") == "production" or os.getenv("RENDER") == "true"
ML_DIR = Path("/tmp/ml_models") if _IS_RENDER else Path(__file__).parent.parent.parent / "ml_models"
ML_DIR.mkdir(parents=True, exist_ok=True)

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

# ── Single-model cache (evict previous before loading new) ──
# Only keeps ONE session in RAM at a time to stay within 512 MB
_current_key: str | None = None
_current_session = None
ONNX_AVAILABLE: bool = False
TF_AVAILABLE:   bool = False  # API compat


def _check_onnx() -> bool:
    global ONNX_AVAILABLE, TF_AVAILABLE
    if ONNX_AVAILABLE:
        return True
    try:
        import onnxruntime  # noqa
        ONNX_AVAILABLE = True
        TF_AVAILABLE   = True
        return True
    except ImportError:
        return False


def _download(fname: str) -> bool:
    dest = ML_DIR / fname
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return True
    url = MODEL_URLS.get(fname)
    if not url:
        return False
    for attempt in range(1, 4):
        logger.info(f"Downloading {fname} attempt {attempt}/3...")
        try:
            if dest.exists():
                dest.unlink()
            urllib.request.urlretrieve(url, str(dest))
            if dest.stat().st_size > 1_000_000:
                logger.info(f"Downloaded {fname} ({dest.stat().st_size/1e6:.1f} MB)")
                return True
            dest.unlink()
        except Exception as e:
            logger.warning(f"Download attempt {attempt} failed: {e}")
            if dest.exists():
                dest.unlink()
            if attempt < 3:
                time.sleep(2)
    return False


def _get_session(key: str, onnx_name: str):
    """Load one ONNX session, evicting the previous one to free RAM."""
    global _current_key, _current_session

    if _current_key == key and _current_session is not None:
        return _current_session

    # Evict previous model to free RAM before loading new one
    if _current_session is not None:
        logger.info(f"Evicting model [{_current_key}] to free RAM")
        del _current_session
        _current_session = None
        _current_key = None
        gc.collect()

    if not _check_onnx():
        return None

    path = ML_DIR / onnx_name
    if not path.exists():
        if not _download(onnx_name):
            return None

    try:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.inter_op_num_threads  = 1
        opts.intra_op_num_threads  = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess = ort.InferenceSession(str(path), sess_options=opts,
                                    providers=["CPUExecutionProvider"])
        _current_key     = key
        _current_session = sess
        logger.info(f"Loaded [{key}] ({path.stat().st_size/1e6:.1f} MB)")
        return sess
    except Exception as e:
        logger.error(f"Failed to load {key}: {e}")
        return None


# Kept for backward compat with API route
def preload_all_models() -> None:
    """No-op — models load on demand to save RAM."""
    _check_onnx()
    logger.info("AI inspection ready (on-demand model loading)")


def ensure_models_loaded() -> bool:
    return _check_onnx()


# ── Preprocessing ─────────────────────────────────────
def _preprocess(image_bytes: bytes, size: tuple) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(size, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    del img
    return np.expand_dims(arr, axis=0)


def _predict(sess, img_arr: np.ndarray) -> float:
    inp = sess.get_inputs()[0].name
    out = sess.run(None, {inp: img_arr})
    result = float(out[0][0][0])
    del img_arr
    return result


# ── Severity ──────────────────────────────────────────
def _severity(prob: float, detected: bool):
    if not detected: return "none", 0.0
    s = prob * 100
    if s < 60:  return "low",      s
    if s < 75:  return "moderate", s
    if s < 90:  return "high",     s
    return "critical", s


def _repair_cost_inr(itype: str, confidence: float, detected: bool):
    if not detected or confidence < 0.5: return 0, 0
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
        if s < 60:   return 5_000,   25_000
        elif s < 75: return 25_000,  1_00_000
        elif s < 90: return 1_00_000,4_00_000
        else:        return 4_00_000,15_00_000


_RECS = {
    "concrete_crack": {
        "low":      ("Hairline cracks detected. Apply epoxy sealant. Monitor monthly.", "soon"),
        "moderate": ("Visible cracks. Epoxy injection recommended.", "soon"),
        "high":     ("Significant structural cracks. Immediate engineer inspection required.", "immediate"),
        "critical": ("CRITICAL: Major structural failure risk. Emergency intervention required.", "immediate"),
    },
    "road_damage": {
        "low":      ("Minor surface wear. Cold mix patching recommended.", "soon"),
        "moderate": ("Pothole detected. Hot mix patching required.", "soon"),
        "high":     ("Severe potholes. Immediate patching required.", "immediate"),
        "critical": ("Dangerous road condition. Full resurfacing required.", "immediate"),
    },
}

def _recommendation(itype: str, severity: str, detected: bool):
    if not detected or severity == "none":
        return "No defects detected. Routine inspection recommended in 6 months.", "monitor"
    return _RECS.get(itype, {}).get(severity, ("Defect detected. Professional assessment required.", "soon"))


def _not_loaded(itype: str, filename: str, classes: list) -> dict:
    return {
        "inspection_type": itype, "model_name": "NOT LOADED",
        "status": "model_weights_not_found",
        "message": f"Model '{filename}' not available.",
        "classes": classes, "severity": "none", "severity_score": 0.0,
        "confidence": 0.0, "mock_prediction": {"predicted_class": classes[0], "confidence": 0.0},
    }


# ── Public inspection functions ───────────────────────
# Each loads only ONE model at a time (not all 3 ensemble models simultaneously)
# to stay within 512 MB RAM on Render free tier.
# The ensemble still runs but sequentially, evicting previous model each time.

def inspect_concrete_crack(image_bytes: bytes) -> dict:
    specs = [
        ("resnet50_crack",    "ResNet50_model.onnx",    (120, 120)),
        ("vgg16_crack",       "VGG16_model.onnx",       (120, 120)),
        ("inceptionv3_crack", "InceptionV3_model.onnx", (150, 150)),
    ]
    preds, names = [], []
    for key, onnx_name, size in specs:
        sess = _get_session(key, onnx_name)
        if sess:
            arr  = _preprocess(image_bytes, size)
            prob = _predict(sess, arr)
            preds.append(prob)
            names.append(key.split("_")[0].upper())
        gc.collect()

    # Release image bytes from caller scope via gc
    if not preds:
        return _not_loaded("concrete_crack", "ResNet50/VGG16/InceptionV3_model.onnx",
                           ["No Crack", "Crack Detected"])

    avg = float(np.mean(preds))
    det = avg > 0.5
    sev, score = _severity(avg, det)
    rec, urg   = _recommendation("concrete_crack", sev, det)
    cmin, cmax = _repair_cost_inr("concrete_crack", avg, det)
    return {
        "inspection_type": "concrete_crack",
        "model_name": f"Ensemble ONNX ({', '.join(names)})",
        "predicted_class": "Crack Detected" if det else "No Crack",
        "confidence": round(avg, 4), "severity": sev,
        "severity_score": round(score, 1), "recommendation": rec,
        "repair_urgency": urg, "estimated_repair_cost_min": cmin,
        "estimated_repair_cost_max": cmax, "currency": "INR",
        "class_probabilities": {"No Crack": round(1-avg,4), "Crack Detected": round(avg,4)},
        "individual_predictions": [round(p,4) for p in preds],
    }


def inspect_surface_crack_ensemble(image_bytes: bytes) -> dict:
    r = inspect_concrete_crack(image_bytes)
    r["inspection_type"] = "surface_crack"
    return r


def inspect_road_damage(image_bytes: bytes) -> dict:
    sess = _get_session("mobilenetv2_road", "crack_model.onnx")
    if sess is None:
        return _not_loaded("road_damage", "crack_model.onnx",
                           ["NEGATIVE (Clean Road)", "POSITIVE (Pothole)"])
    arr  = _preprocess(image_bytes, (160, 160))
    prob = _predict(sess, arr)
    gc.collect()
    det  = prob > 0.5
    sev, score = _severity(prob, det)
    if det and sev == "low": sev = "moderate"
    rec, urg   = _recommendation("road_damage", sev, det)
    cmin, cmax = _repair_cost_inr("road_damage", prob, det)
    return {
        "inspection_type": "road_damage",
        "model_name": "MobileNetV2 ONNX (crack_model.onnx)",
        "predicted_class": "POSITIVE (Pothole)" if det else "NEGATIVE (Clean Road)",
        "confidence": round(prob,4), "severity": sev,
        "severity_score": round(score,1),
        "detections": [{"class":"pothole","confidence":round(prob,4)}] if det else [],
        "total_defects": 1 if det else 0,
        "recommendation": rec, "repair_urgency": urg,
        "estimated_repair_cost_min": cmin, "estimated_repair_cost_max": cmax,
        "currency": "INR",
        "class_probabilities": {"NEGATIVE (Clean Road)":round(1-prob,4),"POSITIVE (Pothole)":round(prob,4)},
    }


def inspect_building_safety(image_bytes: bytes) -> dict:
    return _not_loaded("building_safety", "efficientnetb7_safety.onnx",
                       ["Safe","Minor Damage","Moderate Damage","Severe Damage"])


def save_inspection_image(image_bytes: bytes, itype: str, filename: str, upload_dir: str) -> str:
    save_dir = os.path.join(upload_dir, "inspections")
    os.makedirs(save_dir, exist_ok=True)
    h    = hashlib.md5(image_bytes).hexdigest()[:8]
    path = os.path.join(save_dir, f"{itype}_{h}_{filename}")
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path
