"""
AI Visual Inspection API
========================
Endpoints for all 4 inspection types wired to the trained models.

Models trained in your notebooks:
  Notebook 1 (1 .ipynb): ResNet50_model.h5, VGG16_model.h5, InceptionV3_model.h5
  Notebook 2 (2.ipynb):  crack_model.h5 (MobileNetV2 pothole detector)

Place all .h5 files in: backend/ml_models/
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import json, os, hashlib

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.models.inspection import Inspection, InspectionType, SeverityLevel
from app.models.user import User
from app.services.ai_inspection import (
    inspect_concrete_crack,
    inspect_surface_crack_ensemble,
    inspect_road_damage,
    inspect_building_safety,
    save_inspection_image,
)

router = APIRouter()

MAX_BYTES   = settings.MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class InspectionOut(BaseModel):
    id: UUID
    project_id: Optional[UUID] = None
    inspection_type: InspectionType
    image_filename: Optional[str] = None
    model_name: Optional[str] = None
    predicted_class: Optional[str] = None
    confidence: Optional[float] = None
    severity: SeverityLevel
    severity_score: Optional[float] = None
    recommendation: Optional[str] = None
    repair_urgency: Optional[str] = None
    estimated_repair_cost_min: Optional[float] = None
    estimated_repair_cost_max: Optional[float] = None
    notes: Optional[str] = None
    is_verified: bool
    created_at: datetime
    model_config = {"from_attributes": True, "protected_namespaces": ()}


def _validate_image(file: UploadFile) -> None:
    import pathlib
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: jpg, jpeg, png, bmp, webp"
        )


def _persist(
    db: Session,
    result: dict,
    image_bytes: bytes,
    filename: str,
    inspection_type: InspectionType,
    project_id: Optional[UUID],
    user_id: UUID,
) -> Inspection:
    """Save image to disk and persist result to the DB."""
    save_path = save_inspection_image(image_bytes, inspection_type.value,
                                      filename, settings.UPLOAD_DIR)

    # Map severity string → enum
    severity_val = result.get("severity", "none")
    try:
        severity = SeverityLevel(severity_val)
    except Exception:
        severity = SeverityLevel.NONE

    inspection = Inspection(
        project_id=str(project_id) if project_id else None,
        inspected_by=str(user_id),
        inspection_type=inspection_type,
        image_path=save_path,
        image_filename=filename,
        model_name=result.get("model_name"),
        predicted_class=result.get("predicted_class") or result.get("worst_defect"),
        confidence=result.get("confidence"),
        severity=severity,
        severity_score=result.get("severity_score"),
        detection_boxes=json.dumps(result.get("detections", [])),
        recommendation=result.get("recommendation"),
        repair_urgency=result.get("repair_urgency"),
        estimated_repair_cost_min=result.get("estimated_repair_cost_min"),
        estimated_repair_cost_max=result.get("estimated_repair_cost_max"),
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


# ── 1. Concrete Crack Detection ───────────────────────
@router.post("/concrete-crack",
             summary="Detect cracks in concrete/surface images (ResNet50 + VGG16 + InceptionV3 ensemble)")
async def concrete_crack(
    file: UploadFile = File(..., description="Photo of concrete surface"),
    project_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Uses the ensemble trained in Notebook 1 (1 .ipynb).
    Models: ResNet50_model.h5, VGG16_model.h5, InceptionV3_model.h5
    Classes: No Crack / Crack Detected
    """
    _validate_image(file)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 50MB)")

    result  = inspect_concrete_crack(content)
    saved   = _persist(db, result, content, file.filename or "image.jpg",
                       InspectionType.CONCRETE_CRACK, project_id, current_user.id)
    return {**result, "inspection_id": str(saved.id)}


# ── 2. Surface Crack Ensemble ─────────────────────────
@router.post("/surface-crack",
             summary="Surface crack ensemble detection (same as concrete-crack)")
async def surface_crack(
    file: UploadFile = File(...),
    project_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Same ensemble model as concrete-crack, labelled as surface_crack in history.
    """
    _validate_image(file)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    result  = inspect_surface_crack_ensemble(content)
    saved   = _persist(db, result, content, file.filename or "image.jpg",
                       InspectionType.SURFACE_CRACK, project_id, current_user.id)
    return {**result, "inspection_id": str(saved.id)}


# ── 3. Road Damage / Pothole Detection ────────────────
@router.post("/road-damage",
             summary="Detect potholes and road damage (MobileNetV2 from Notebook 2)")
async def road_damage(
    file: UploadFile = File(..., description="Photo of road surface"),
    project_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Uses MobileNetV2 trained in Notebook 2 (2.ipynb).
    Model file: crack_model.h5
    Classes: NEGATIVE (Clean Road) / POSITIVE (Pothole)
    """
    _validate_image(file)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    result  = inspect_road_damage(content)
    saved   = _persist(db, result, content, file.filename or "image.jpg",
                       InspectionType.ROAD_DAMAGE, project_id, current_user.id)
    return {**result, "inspection_id": str(saved.id)}


# ── 4. Building Safety ────────────────────────────────
@router.post("/building-safety",
             summary="Assess building structural safety (model not yet trained)")
async def building_safety(
    file: UploadFile = File(...),
    project_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Awaiting trained model (efficientnetb7_safety.h5).
    Returns model_not_loaded response until weights are added.
    """
    _validate_image(file)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    result  = inspect_building_safety(content)
    saved   = _persist(db, result, content, file.filename or "image.jpg",
                       InspectionType.BUILDING_SAFETY, project_id, current_user.id)
    return {**result, "inspection_id": str(saved.id)}


# ── Model status ──────────────────────────────────────
@router.get("/models/status", summary="Check which AI models are loaded")
def model_status(_: User = Depends(get_current_active_user)):
    """Shows which model weight files are present and loaded."""
    from pathlib import Path
    from app.services.ai_inspection import _models, ML_DIR

    model_files = {
        "concrete_crack_resnet50":    "ResNet50_model.h5",
        "concrete_crack_vgg16":       "VGG16_model.h5",
        "concrete_crack_inceptionv3": "InceptionV3_model.h5",
        "road_damage_mobilenet":      "crack_model.h5",
        "building_safety":            "efficientnetb7_safety.h5",
    }

    status_map = {}
    for key, filename in model_files.items():
        path = ML_DIR / filename
        status_map[key] = {
            "filename":    filename,
            "file_exists": path.exists(),
            "loaded":      key in _models,
            "size_mb":     round(path.stat().st_size / 1_048_576, 1) if path.exists() else 0,
        }
    return {
        "ml_models_dir":        str(ML_DIR),
        "models":               status_map,
        "tensorflow_available": _check_tf(),
    }


def _check_tf() -> bool:
    try:
        import tensorflow
        return True
    except ImportError:
        return False


# ── History ───────────────────────────────────────────
@router.get("/history", response_model=List[InspectionOut],
            summary="Inspection history for current user")
def get_history(
    project_id: Optional[UUID] = None,
    inspection_type: Optional[InspectionType] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = db.query(Inspection).filter(Inspection.inspected_by == str(current_user.id))
    if project_id:
        q = q.filter(Inspection.project_id == str(project_id))
    if inspection_type:
        q = q.filter(Inspection.inspection_type == inspection_type)
    return q.order_by(Inspection.created_at.desc()).limit(limit).all()


# ── Stats ─────────────────────────────────────────────
@router.get("/stats", summary="Inspection statistics summary")
def inspection_stats(
    project_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    q = db.query(Inspection)
    if project_id:
        q = q.filter(Inspection.project_id == str(project_id))
    rows = q.all()
    by_type:     dict = {}
    by_severity: dict = {}
    for r in rows:
        t = r.inspection_type.value if hasattr(r.inspection_type, 'value') else str(r.inspection_type)
        s = r.severity.value if hasattr(r.severity, 'value') else str(r.severity)
        by_type[t]     = by_type.get(t, 0) + 1
        by_severity[s] = by_severity.get(s, 0) + 1

    return {
        "total_inspections": len(rows),
        "by_type":           by_type,
        "by_severity":       by_severity,
        "critical_count":    by_severity.get("critical", 0),
        "high_count":        by_severity.get("high", 0),
    }


# ── Get by ID ─────────────────────────────────────────
@router.get("/{inspection_id}", response_model=InspectionOut,
            summary="Get a specific inspection result")
def get_inspection(
    inspection_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    ins = db.query(Inspection).filter(Inspection.id == str(inspection_id)).first()
    if not ins:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return ins


# ── Verify ────────────────────────────────────────────
@router.patch("/{inspection_id}/verify", response_model=InspectionOut,
              summary="Mark inspection as engineer-verified")
def verify_inspection(
    inspection_id: UUID,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    ins = db.query(Inspection).filter(Inspection.id == str(inspection_id)).first()
    if not ins:
        raise HTTPException(status_code=404, detail="Inspection not found")
    ins.is_verified = True
    if notes:
        ins.notes = notes
    db.commit()
    db.refresh(ins)
    return ins


