"""
AI Visual Inspection Service
==============================
Wired to YOUR trained models from the notebooks:

Notebook 1 (1 .ipynb) — Surface Crack Detection
  - ResNet50_model.h5   → image size (120,120), binary sigmoid
  - VGG16_model.h5      → image size (120,120), binary sigmoid
  - InceptionV3_model.h5 → image size (150,150), binary sigmoid
  Classes: 0=Negative (no crack), 1=Positive (crack)
  Prediction: model.predict(img) > 0.5 → int

Notebook 2 (2.ipynb) — Pothole/Road Damage Detection
  - crack_model.h5 → MobileNetV2, image size (160,160), binary sigmoid
  Classes: 0=NEGATIVE (clean road), 1=POSITIVE (pothole)
  Prediction: model.predict(img) > 0.5 → int

All .h5 files must be placed in: backend/ml_models/
"""
from __future__ import annotations
import os
import io
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).parent.parent.parent / "ml_models"
ML_DIR.mkdir(exist_ok=True)

# ── Lazy model cache ──────────────────────────────────
_models: dict = {}


# ── Image preprocessing ───────────────────────────────
def _preprocess(image_bytes: bytes, size: tuple) -> np.ndarray:
    """Load image bytes → resize → normalize → add batch dim."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(size)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # (1, H, W, 3)


# ── Load Keras model (lazy, cached) ───────────────────
def _load_model(name: str, h5_path: Path):
    if name in _models:
        return _models[name]
    if not h5_path.exists():
        logger.warning(f"Model weights not found: {h5_path}")
        return None
    try:
        import tensorflow as tf
        model = tf.keras.models.load_model(str(h5_path))
        _models[name] = model
        logger.info(f"Loaded model: {name} from {h5_path.name}")
        return model
    except Exception as e:
        logger.error(f"Failed to load {name}: {e}")
        return None


# ── Severity from probability ─────────────────────────
def _severity(prob: float, detected: bool) -> tuple[str, float]:
    """Map detection probability to severity level."""
    if not detected:
        return "none", 0.0
    score = prob * 100
    if score < 60:  return "low",      score
    if score < 75:  return "moderate", score
    if score < 90:  return "high",     score
    return "critical", score


# ── Repair cost estimates (PKR) ───────────────────────
REPAIR_COSTS = {
    "concrete_crack": {
        "none":     (0, 0),
        "low":      (5_000, 15_000),
        "moderate": (20_000, 60_000),
        "high":     (80_000, 200_000),
        "critical": (250_000, 800_000),
    },
    "road_damage": {
        "none":     (0, 0),
        "low":      (10_000, 30_000),
        "moderate": (50_000, 150_000),
        "high":     (200_000, 600_000),
        "critical": (700_000, 2_000_000),
    },
}


def _recommendation(inspection_type: str, severity: str, detected: bool) -> tuple[str, str]:
    """Returns (recommendation_text, urgency)."""
    if not detected or severity == "none":
        return "No defects detected. Schedule routine inspection in 6 months.", "monitor"

    recs = {
        "concrete_crack": {
            "low":      ("Hairline cracks detected. Apply epoxy injection or crack sealant. Monitor for growth.", "soon"),
            "moderate": ("Structural engineer assessment required. Apply polymer-modified mortar repair.", "soon"),
            "high":     ("Significant cracking found. Immediate structural engineer inspection required.", "immediate"),
            "critical": ("CRITICAL: Stop use. Immediate structural intervention required.", "immediate"),
        },
        "road_damage": {
            "low":      ("Minor road surface damage. Apply cold mix patching. Mark for scheduled maintenance.", "soon"),
            "moderate": ("Pothole detected. Hot mix patching required. Mark for traffic safety.", "soon"),
            "high":     ("Severe pothole. Immediate patching required to prevent vehicle damage.", "immediate"),
            "critical": ("Dangerous road condition. Close road immediately. Full resurfacing required.", "immediate"),
        },
    }
    type_recs = recs.get(inspection_type, {})
    rec_text, urgency = type_recs.get(severity, ("Defect detected. Professional assessment required.", "soon"))
    return rec_text, urgency


# ── Not loaded response ───────────────────────────────
def _not_loaded(inspection_type: str, model_filename: str, classes: list) -> dict:
    return {
        "inspection_type": inspection_type,
        "model_name": "NOT LOADED",
        "status": "model_weights_not_found",
        "message": (
            f"Place '{model_filename}' in backend/ml_models/. "
            f"Train from notebook and save with: model.save('{model_filename}')"
        ),
        "classes": classes,
        "mock_prediction": {
            "note": "Placeholder — load model weights for real predictions.",
            "predicted_class": classes[0],
            "confidence": 0.0,
            "severity": "unknown",
        },
    }


# ══════════════════════════════════════════════════════
# PUBLIC API — one function per inspection type
# ══════════════════════════════════════════════════════

def inspect_concrete_crack(image_bytes: bytes) -> dict:
    """
    Notebook 1: Surface Crack Detection.
    Ensemble vote from ResNet50 + VGG16 + InceptionV3.
    Falls back to single available model if others missing.
    """
    # Model specs from notebook 1: exact sizes used during training
    model_specs = [
        ("resnet50_crack",    ML_DIR / "ResNet50_model.h5",    (120, 120)),
        ("vgg16_crack",       ML_DIR / "VGG16_model.h5",       (120, 120)),
        ("inceptionv3_crack", ML_DIR / "InceptionV3_model.h5", (150, 150)),
    ]

    predictions = []
    loaded_names = []

    for name, path, size in model_specs:
        model = _load_model(name, path)
        if model:
            arr  = _preprocess(image_bytes, size)
            prob = float(model.predict(arr, verbose=0)[0][0])
            predictions.append(prob)
            loaded_names.append(name.replace("_crack", "").upper())

    if not predictions:
        return _not_loaded("concrete_crack",
                           "ResNet50_model.h5 / VGG16_model.h5 / InceptionV3_model.h5",
                           ["No Crack", "Crack Detected"])

    # Soft voting ensemble: average probability
    avg_prob = float(np.mean(predictions))
    detected = avg_prob > 0.5
    severity, score = _severity(avg_prob, detected)
    rec, urgency    = _recommendation("concrete_crack", severity, detected)
    c_min, c_max    = REPAIR_COSTS["concrete_crack"].get(severity, (0, 0))

    return {
        "inspection_type":   "concrete_crack",
        "model_name":        f"Ensemble ({', '.join(loaded_names)})" if len(loaded_names) > 1 else loaded_names[0],
        "predicted_class":   "Crack Detected" if detected else "No Crack",
        "confidence":        round(avg_prob, 4),
        "severity":          severity,
        "severity_score":    round(score, 1),
        "recommendation":    rec,
        "repair_urgency":    urgency,
        "estimated_repair_cost_min": c_min,
        "estimated_repair_cost_max": c_max,
        "class_probabilities": {
            "No Crack":       round(1 - avg_prob, 4),
            "Crack Detected": round(avg_prob, 4),
        },
        "ensemble_models_used": loaded_names,
        "individual_predictions": [round(p, 4) for p in predictions],
    }


def inspect_surface_crack_ensemble(image_bytes: bytes) -> dict:
    """
    Same ensemble as concrete crack — reuse.
    """
    result = inspect_concrete_crack(image_bytes)
    result["inspection_type"] = "surface_crack"
    return result


def inspect_road_damage(image_bytes: bytes) -> dict:
    """
    Notebook 2: Pothole detection — MobileNetV2.
    Model file: crack_model.h5
    Image size: 160×160
    Classes: 0=NEGATIVE (clean road), 1=POSITIVE (pothole)
    """
    model = _load_model("road_damage_mobilenet", ML_DIR / "crack_model.h5")

    if model is None:
        return _not_loaded("road_damage", "crack_model.h5",
                           ["NEGATIVE (Clean Road)", "POSITIVE (Pothole)"])

    arr  = _preprocess(image_bytes, (160, 160))
    prob = float(model.predict(arr, verbose=0)[0][0])
    detected = prob > 0.5
    severity, score = _severity(prob, detected)
    # Potholes are always at least moderate severity
    if detected and severity == "low":
        severity = "moderate"
    rec, urgency = _recommendation("road_damage", severity, detected)
    c_min, c_max = REPAIR_COSTS["road_damage"].get(severity, (0, 0))

    return {
        "inspection_type":   "road_damage",
        "model_name":        "MobileNetV2 Pothole Detector",
        "predicted_class":   "POSITIVE (Pothole)" if detected else "NEGATIVE (Clean Road)",
        "confidence":        round(prob, 4),
        "severity":          severity,
        "severity_score":    round(score, 1),
        "detections":        [{"class": "pothole", "confidence": round(prob, 4), "bbox": []}] if detected else [],
        "total_defects":     1 if detected else 0,
        "worst_defect":      "pothole" if detected else "none",
        "recommendation":    rec,
        "repair_urgency":    urgency,
        "estimated_repair_cost_min": c_min,
        "estimated_repair_cost_max": c_max,
        "class_probabilities": {
            "NEGATIVE (Clean Road)": round(1 - prob, 4),
            "POSITIVE (Pothole)":    round(prob, 4),
        },
    }


def inspect_building_safety(image_bytes: bytes) -> dict:
    """
    Building safety — not yet trained.
    Returns a clear message directing the user to train the model.
    """
    return _not_loaded(
        "building_safety",
        "efficientnetb7_safety.h5",
        ["Safe", "Minor Damage", "Moderate Damage", "Severe Damage"],
    )


# ── Save inspection image to disk ────────────────────
def save_inspection_image(image_bytes: bytes, inspection_type: str,
                          filename: str, upload_dir: str) -> str:
    """Save uploaded image and return the saved file path."""
    save_dir = os.path.join(upload_dir, "inspections")
    os.makedirs(save_dir, exist_ok=True)
    img_hash = hashlib.md5(image_bytes).hexdigest()[:8]
    save_name = f"{inspection_type}_{img_hash}_{filename}"
    save_path = os.path.join(save_dir, save_name)
    with open(save_path, "wb") as f:
        f.write(image_bytes)
    return save_path
