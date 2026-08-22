"""
Drawing Takeoff API
===================
Upload a DXF drawing → element detection → engineer verification → Measurement Book.

PRINCIPLE: AI reads. Formula engine calculates. Engineer approves.
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.measurement import MeasurementBook, MeasurementItem
from app.services.drawing_analyzer import (
    analyze_dxf_drawing,
    elements_to_mb_items,
    DrawingElement,
    DetectionStatus,
    Confidence,
)
from app.crud import project as project_crud

router = APIRouter()
MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


# ── Schemas ───────────────────────────────────────────────────────────────────

class DimensionIn(BaseModel):
    value: Optional[float] = None
    unit: str = "m"
    source: str = "user_input"


class VerifiedElementIn(BaseModel):
    """Engineer-verified element — sent back after review."""
    mark: str
    element_type: str
    description: str
    length:  Optional[DimensionIn] = None
    width:   Optional[DimensionIn] = None
    height:  Optional[DimensionIn] = None
    depth:   Optional[DimensionIn] = None
    nos:     Optional[DimensionIn] = None
    unit: str = "m3"
    category: str = "rcc"
    formula: str = ""


class SendToMBRequest(BaseModel):
    project_id: UUID
    building_id: Optional[UUID] = None
    boq_id: Optional[UUID] = None
    mb_title: str = "Drawing Takeoff"
    storey_height_m: float = 3.0
    verified_elements: List[dict]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/analyze", summary="Analyze DXF drawing — extract element schedule")
async def analyze_drawing(
    file: UploadFile = File(...),
    units: str = Form("mm", description="Drawing units: mm, cm, m, ft, in"),
    db: Session = Depends(get_db),
    cu: User = Depends(get_current_active_user),
):
    """
    STEP 1: Upload DXF drawing for element detection.

    Returns:
    - drawing_info: type, scale, floor, units
    - elements: detected C1/B1/F1/S1 etc. with dimensions from schedule text
    - validation_checks: consistency between plan and schedule
    - missing_info: what the engineer must fill in
    - warnings: anything unreliable

    DOES NOT compute quantities. That happens after engineer verification.
    """
    fname = file.filename or ""
    if not fname.lower().endswith(".dxf"):
        raise HTTPException(
            400,
            "Only DXF files are accepted. "
            "Save your DWG as DXF 2010 from AutoCAD: File → Save As → DXF."
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit")

    analysis = analyze_dxf_drawing(content, drawing_units=units)
    result   = analysis.to_dict()

    # Annotate each element with instructions for the engineer
    for el in result["elements"]:
        el["engineer_action"] = "verify"   # default: needs verification
        # Elements where all required dims are present = suggest auto-accept
        needed = _required_dims(el["element_type"])
        all_present = all(el.get(k) and el[k]["value"] is not None for k in needed)
        if all_present and el["confidence"] == "high":
            el["engineer_action"] = "suggested_accept"
        elif el["status"] == "conflict_detected":
            el["engineer_action"] = "resolve_conflict"

    return {
        "filename": fname,
        "units_used": units,
        "analysis": result,
        "instructions": {
            "step1": "Review all detected elements below.",
            "step2": "Edit any dimensions marked as 'engineer_input_required'.",
            "step3": "Accept or reject each element.",
            "step4": "Click 'Send to Measurement Book' to create quantities.",
            "warning": "No quantities are calculated until you verify and send to Measurement Book.",
        },
    }


def _required_dims(element_type: str) -> list[str]:
    return {
        "column":  ["width", "height", "depth", "nos"],  # B, D, H, Nos
        "beam":    ["width", "height", "length", "nos"],  # B, D, L, Nos
        "footing": ["length", "width", "depth", "nos"],
        "slab":    ["length", "width", "depth", "nos"],   # L, B, T, Nos
        "wall":    ["length", "height", "depth", "nos"],
        "door":    ["width", "height", "nos"],
        "window":  ["width", "height", "nos"],
    }.get(element_type, [])


@router.post("/send-to-mb", summary="Send verified elements to Measurement Book")
def send_to_measurement_book(
    payload: SendToMBRequest,
    db: Session = Depends(get_db),
    cu: User = Depends(get_current_active_user),
):
    """
    STEP 2: After engineer verification, create Measurement Book entries.

    - Creates a new MeasurementBook for the project
    - Adds one row per element group (heading + items)
    - Formula display is auto-computed by Measurement Book API
    - Returns the MB ID for the engineer to review quantities
    """
    # Validate project
    project = project_crud.get_project_by_id(db, payload.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if not payload.verified_elements:
        raise HTTPException(422, "No verified elements provided")

    # Create measurement book
    count = db.query(MeasurementBook).filter(
        MeasurementBook.project_id == str(payload.project_id)
    ).count()

    mb = MeasurementBook(
        project_id=str(payload.project_id),
        building_id=str(payload.building_id) if payload.building_id else None,
        boq_id=str(payload.boq_id) if payload.boq_id else None,
        mb_number=f"MB-{count+1:03d}-DWG",
        title=payload.mb_title,
        description="Auto-generated from drawing takeoff — engineer verified",
        prepared_by=str(cu.id),
        date_of_measurement=datetime.utcnow(),
    )
    db.add(mb)
    db.flush()

    # Convert elements to MB items
    items_data = elements_to_mb_items(payload.verified_elements, payload.storey_height_m)
    created_items = []

    # Import compute function from measurement API
    from app.api.v1.measurement import _compute_quantity as cq

    for item_data in items_data:
        item = MeasurementItem(
            book_id=str(mb.id),
            sort_order=item_data.get("sort_order", 0),
            is_heading=item_data.get("is_heading", False),
            item_ref=item_data.get("item_ref"),
            description=item_data["description"],
            unit=item_data.get("unit"),
            length=item_data.get("length"),
            width=item_data.get("width"),
            height=item_data.get("height"),
            nos=item_data.get("nos", 1.0),
            is_manual_override=False,
        )
        # Compute quantity and formula using existing engine
        qty, formula = cq(item)
        item.quantity = qty
        item.formula_display = formula
        db.add(item)
        created_items.append({
            "description": item.description,
            "quantity": qty,
            "unit": item.unit,
            "formula": formula,
        })

    db.commit()

    return {
        "measurement_book_id": str(mb.id),
        "mb_number": mb.mb_number,
        "items_created": len(created_items),
        "items": created_items,
        "next_step": f"Review Measurement Book {mb.mb_number} to verify quantities, then link to BOQ.",
    }


@router.get("/formula-guide", summary="Engineering formula guide for all element types")
def formula_guide(_: User = Depends(get_current_active_user)):
    """Returns the civil engineering formulas used for each element type."""
    return {
        "formulas": {
            "column":  {
                "formula": "B × D × H × Nos",
                "description": "Breadth × Depth × Height × Number",
                "unit": "m³",
                "example": "0.30 × 0.30 × 3.20 × 12 = 3.456 m³",
            },
            "beam": {
                "formula": "B × D × L × Nos",
                "description": "Width × Depth × Length × Number",
                "unit": "m³",
                "example": "0.23 × 0.45 × 4.50 × 8 = 3.726 m³",
            },
            "slab": {
                "formula": "L × B × Thickness × Nos",
                "description": "Length × Width × Thickness × Number",
                "unit": "m³",
                "example": "10.0 × 8.0 × 0.125 × 1 = 10.0 m³",
            },
            "footing": {
                "formula": "L × B × D × Nos",
                "description": "Length × Width × Depth × Number",
                "unit": "m³",
                "example": "1.50 × 1.50 × 0.30 × 12 = 8.10 m³",
            },
            "excavation": {
                "formula": "L × B × D × Nos",
                "description": "Length × Width × Depth × Number",
                "unit": "m³",
                "example": "1.80 × 1.80 × 1.50 × 12 = 58.32 m³",
            },
            "wall_masonry": {
                "formula": "L × H × Thickness × Nos − openings",
                "description": "Wall Length × Height × Thickness − door/window deductions",
                "unit": "m³",
                "example": "(10.0 × 3.0 × 0.23) − (0.9 × 2.1 × 0.23 × 4) = 5.162 m³",
            },
            "plaster": {
                "formula": "L × H × Nos − openings",
                "description": "Wall Length × Height − openings",
                "unit": "m²",
                "example": "10.0 × 3.0 − (0.9×2.1 × 4) − (1.2×1.2 × 6) = 14.08 m²",
            },
            "steel_reinforcement": {
                "formula": "d² / 162 × L × Nos",
                "description": "Bar dia² ÷ 162 × bar length × number of bars (gives kg)",
                "unit": "kg",
                "example": "12² / 162 × 3.5 × 24 = 74.67 kg",
            },
            "flooring": {
                "formula": "L × B × Nos + wastage",
                "description": "Length × Width × Number + wastage %",
                "unit": "m²",
                "example": "4.5 × 3.0 × 1 × 1.10 (10% wastage) = 14.85 m²",
            },
            "formwork_column": {
                "formula": "2 × (B + D) × H × Nos",
                "description": "Perimeter × Height × Number",
                "unit": "m²",
                "example": "2 × (0.30 + 0.30) × 3.20 × 12 = 46.08 m²",
            },
        },
        "note": "All formulas are deterministic. AI extracts dimensions. Formula engine calculates. Engineer verifies.",
    }
