"""
DXF Upload API
==============
Accepts AutoCAD DXF files and returns:
  - Building footprint area (out-to-out slab area)
  - Boundary perimeter
  - Wall lengths (external / internal / total)
  - Door / window counts
  - Boundary candidates (for user selection)
  - Full diagnostics
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.crud import building as building_crud
from app.crud import project as project_crud
from app.models.user import User
from app.services.dxf_parser import parse_dxf_bytes
from app.schemas.building import BuildingUpdate

router = APIRouter()

MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload/{project_id}", summary="Upload DXF and extract building geometry")
async def upload_dxf(
    project_id: UUID,
    file:               UploadFile = File(...),
    units:              str  = Form("mm"),
    apply_to_building:  str  = Form("false"),   # "true" | "false" | "extract"
    db:           Session    = Depends(get_db),
    current_user: User       = Depends(get_current_active_user),
):
    """
    Parse an uploaded DXF file.

    Returns extracted building geometry including:
    - out-to-out building footprint area (m² and ft²)
    - boundary perimeter
    - wall lengths
    - door / window counts
    - boundary candidates list
    - full diagnostics panel
    """
    fname = (file.filename or "").lower()
    if not fname.endswith(".dxf"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only DXF files are accepted. "
                "In AutoCAD: File → Save As → DXF 2010 (ASCII format)."
            ),
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum {settings.MAX_FILE_SIZE_MB} MB.",
        )

    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ── Parse ─────────────────────────────────────────
    result = parse_dxf_bytes(content, units=units)
    data   = result.to_dict()

    # ── Optionally apply to building ──────────────────
    should_apply = str(apply_to_building).lower() in ("true", "extract & apply", "1")
    applied      = False

    if should_apply:
        buildings = building_crud.get_buildings_by_project(db, project_id)
        if buildings:
            b = buildings[0]

            # Build update payload from extracted data
            upd: dict = {}

            # Slab / plot dimensions from footprint
            footprint = data["building_footprint_area_m2"]
            if footprint > 0:
                w = data["diagnostics"].get("selected_boundary", {}).get("width_m", 0)
                h = data["diagnostics"].get("selected_boundary", {}).get("height_m", 0)
                if w > 0 and h > 0:
                    upd["plot_length"] = round(w, 2)
                    upd["plot_width"]  = round(h, 2)
                    upd["slab_length"] = round(w, 2)
                    upd["slab_width"]  = round(h, 2)
                else:
                    # Fall back to square root approximation
                    side = round(footprint ** 0.5, 2)
                    upd["plot_length"] = side
                    upd["plot_width"]  = side
                    upd["slab_length"] = side
                    upd["slab_width"]  = side

            # Wall lengths
            ext_wall = data.get("external_wall_length_m", 0)
            int_wall = data.get("internal_wall_length_m", 0)
            if ext_wall > 0:
                upd["total_external_wall_length"] = round(ext_wall, 2)
            if int_wall > 0:
                upd["total_internal_wall_length"] = round(int_wall, 2)

            # Doors / windows
            if data["num_doors"] > 0:
                upd["num_doors"] = data["num_doors"]
            if data["num_windows"] > 0:
                upd["num_windows"] = data["num_windows"]

            if upd:
                building_crud.update_building(db, b, BuildingUpdate(**upd))
                applied = True
        else:
            data["warnings"].append(
                "No building found for this project. "
                "Create a building first, then re-upload to apply dimensions."
            )

    return {
        "project_id":          str(project_id),
        "filename":            file.filename,
        "units_used":          units,
        "units_detected":      data["units_detected"],
        "scale_factor":        data["scale_factor"],
        "applied_to_building": applied,

        # ── Primary BOQ results ──────────────────────
        "extracted": {
            # Building footprint (main result)
            "building_footprint_area_m2":  data["building_footprint_area_m2"],
            "building_footprint_area_ft2": data["building_footprint_area_ft2"],
            "boundary_perimeter_m":        data["boundary_perimeter_m"],
            "boundary_perimeter_ft":       data["boundary_perimeter_ft"],
            "slab_area_m2":                data["slab_area_m2"],

            # Legacy keys (DXFPage backward compat)
            "total_floor_area_m2":         data["building_footprint_area_m2"],
            "total_wall_length_m":         data["total_wall_length_m"],

            # Wall detail
            "external_wall_length_m":      data["external_wall_length_m"],
            "internal_wall_length_m":      data["internal_wall_length_m"],

            # Openings
            "num_doors":   data["num_doors"],
            "num_windows": data["num_windows"],

            # Room / sub-area list
            "rooms":       data["rooms"],

            # Boundary candidates (for UI selector)
            "boundary_candidates": data["boundary_candidates"],

            # Raw entity counts
            "entity_counts": data["entity_counts"],
        },

        # ── Full diagnostics ─────────────────────────
        "diagnostics": data["diagnostics"],
        "warnings":    data["warnings"],
    }


@router.get("/layers-guide", summary="DXF layer naming conventions guide")
def layers_guide(_: User = Depends(get_current_active_user)):
    return {
        "wall_layers":   ["WALL", "WALLS", "A-WALL", "EXT_WALL", "INT_WALL", "PARTITION"],
        "door_layers":   ["DOOR", "DOORS", "DR", "PINTU"],
        "window_layers": ["WINDOW", "WIN", "CASEMENT", "JENDELA"],
        "room_layers":   ["ROOM", "ROOMS", "FLOOR", "AREA", "SLAB"],
        "avoid_layers":  ["TITLEBLOCK", "TITLE", "BORDER", "FRAME", "VIEWPORT"],
        "tips": [
            "For best results, draw external and internal walls on separate layers.",
            "Close all polylines that define room or building boundaries.",
            "Place door/window blocks on layers named DOOR or WINDOW.",
            "Set $INSUNITS in your DXF — AutoCAD: UNITS command → set correctly.",
            "If OLE2FRAME is detected, explode it in AutoCAD and save as DXF 2010 ASCII.",
            "Layer 0 geometry is always included in area extraction.",
        ],
    }
