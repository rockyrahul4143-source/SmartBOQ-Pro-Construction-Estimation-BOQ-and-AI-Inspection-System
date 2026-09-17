"""
DXF Upload API  — v3
=====================
Accepts AutoCAD DXF files and returns:
  - Building footprint (out-to-out slab area) in m² and ft²
  - Boundary perimeter
  - Wall lengths (external / internal / total)
  - Door / window counts
  - Boundary candidates with SVG preview paths
  - Full diagnostics panel data

Endpoints
---------
POST /api/v1/dxf/upload/{project_id}   — parse + optionally apply to building
GET  /api/v1/dxf/layers-guide          — layer naming tips
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


@router.post(
    "/upload/{project_id}",
    summary="Upload DXF and extract building geometry",
)
async def upload_dxf(
    project_id:         UUID,
    file:               UploadFile = File(...),
    units:              str  = Form("mm"),
    apply_to_building:  str  = Form("false"),
    selected_boundary:  int  = Form(-1),   # 0-based index; -1 = auto-select
    db:           Session    = Depends(get_db),
    current_user: User       = Depends(get_current_active_user),
):
    """
    Parse an uploaded DXF file.

    - **units**: drawing units hint (mm / cm / m / ft / in)
    - **apply_to_building**: "true" to write extracted dimensions to the first building
    - **selected_boundary**: index into boundary_candidates to use; -1 = auto-select best

    Returns extracted building geometry including out-to-out building footprint area,
    boundary perimeter, wall lengths, door/window counts, boundary candidates list,
    SVG preview paths, and full diagnostics.
    """
    # ── Validate file ─────────────────────────────────────────────────────────
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

    # ── Validate project ──────────────────────────────────────────────────────
    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # ── Parse DXF ────────────────────────────────────────────────────────────
    result = parse_dxf_bytes(content, units=units)
    data   = result.to_dict()

    # ── Allow caller to override the auto-selected boundary ──────────────────
    candidates = data.get("boundary_candidates", [])
    if 0 <= selected_boundary < len(candidates):
        chosen = candidates[selected_boundary]
        # Override primary metrics with the user-chosen candidate
        data["building_footprint_area_m2"]  = chosen["area_m2"]
        data["building_footprint_area_ft2"] = chosen["area_ft2"]
        data["boundary_perimeter_m"]        = chosen["perimeter_m"]
        data["boundary_perimeter_ft"]       = chosen["perimeter_ft"]
        data["slab_area_m2"]                = chosen["area_m2"]
        data["total_floor_area_m2"]         = chosen["area_m2"]
        # Re-tag is_selected
        for i, c in enumerate(candidates):
            c["is_selected"] = (i == selected_boundary)
        if "selected_boundary" in data.get("diagnostics", {}):
            data["diagnostics"]["selected_boundary"] = {
                "area_m2":     chosen["area_m2"],
                "area_ft2":    chosen["area_ft2"],
                "perimeter_m": chosen["perimeter_m"],
                "width_m":     chosen["width_m"],
                "height_m":    chosen["height_m"],
                "user_selected": True,
            }
        data["warnings"].append(
            f"User manually selected boundary #{selected_boundary + 1} "
            f"({chosen['area_m2']} m²)."
        )

    # ── Optionally apply to building ──────────────────────────────────────────
    should_apply = str(apply_to_building).lower() in ("true", "1", "yes")
    applied      = False

    if should_apply:
        buildings = building_crud.get_buildings_by_project(db, project_id)
        if buildings:
            b   = buildings[0]
            upd: dict = {}

            footprint = data["building_footprint_area_m2"]
            if footprint > 0:
                # Prefer exact W×H from selected boundary
                sel = data.get("diagnostics", {}).get("selected_boundary", {})
                w   = sel.get("width_m",  0)
                h   = sel.get("height_m", 0)

                # Also look in candidates list (user-selected or auto)
                if not (w > 0 and h > 0):
                    for c in candidates:
                        if c.get("is_selected"):
                            w = c.get("width_m",  0)
                            h = c.get("height_m", 0)
                            break

                if w > 0 and h > 0:
                    upd["plot_length"] = round(w, 3)
                    upd["plot_width"]  = round(h, 3)
                    upd["slab_length"] = round(w, 3)
                    upd["slab_width"]  = round(h, 3)
                else:
                    # Fallback: approximate from area
                    side = round(footprint ** 0.5, 3)
                    upd["plot_length"] = side
                    upd["plot_width"]  = side
                    upd["slab_length"] = side
                    upd["slab_width"]  = side

            ext_wall = data.get("external_wall_length_m", 0)
            int_wall = data.get("internal_wall_length_m", 0)
            if ext_wall > 0:
                upd["total_external_wall_length"] = round(ext_wall, 3)
            if int_wall > 0:
                upd["total_internal_wall_length"] = round(int_wall, 3)

            if data["num_doors"] > 0:
                upd["num_doors"]   = data["num_doors"]
            if data["num_windows"] > 0:
                upd["num_windows"] = data["num_windows"]

            if upd:
                building_crud.update_building(db, b, BuildingUpdate(**upd))
                applied = True
        else:
            data["warnings"].append(
                "No building found for this project. "
                "Create a building first, then re-upload with 'Extract & Apply'."
            )

    # ── Assemble response ─────────────────────────────────────────────────────
    return {
        "project_id":          str(project_id),
        "filename":            file.filename,
        "file_size_kb":        round(len(content) / 1024, 1),
        "units_used":          data["units_used"],
        "units_detected":      data["units_detected"],
        "scale_factor":        data["scale_factor"],
        "applied_to_building": applied,

        # ── Primary BOQ result values ────────────────────────────────────────
        "extracted": {
            # Out-to-out building footprint (primary BOQ value)
            "building_footprint_area_m2":  data["building_footprint_area_m2"],
            "building_footprint_area_ft2": data["building_footprint_area_ft2"],
            "boundary_perimeter_m":        data["boundary_perimeter_m"],
            "boundary_perimeter_ft":       data["boundary_perimeter_ft"],
            "slab_area_m2":                data["slab_area_m2"],

            # Legacy compatibility keys
            "total_floor_area_m2":         data["building_footprint_area_m2"],
            "total_wall_length_m":         data["total_wall_length_m"],

            # Wall breakdown
            "external_wall_length_m":      data["external_wall_length_m"],
            "internal_wall_length_m":      data["internal_wall_length_m"],

            # Openings
            "num_doors":   data["num_doors"],
            "num_windows": data["num_windows"],

            # Sub-areas (detected room outlines)
            "rooms":       data["rooms"],

            # Boundary candidates (with SVG preview paths)
            "boundary_candidates": data["boundary_candidates"],

            # Entity counts (for diagnostics panel)
            "entity_counts": data["entity_counts"],

            # SVG viewport info for the full drawing preview
            "svg_viewbox": (
                data["boundary_candidates"][0].get("svg_viewbox", "0 0 480 360")
                if data["boundary_candidates"] else "0 0 480 360"
            ),
        },

        # ── Full diagnostics ─────────────────────────────────────────────────
        "diagnostics": data["diagnostics"],
        "warnings":    data["warnings"],
    }


@router.get("/layers-guide", summary="DXF layer naming conventions guide")
def layers_guide(_: User = Depends(get_current_active_user)):
    """Returns recommended DXF layer naming conventions and usage tips."""
    return {
        "wall_layers": [
            "WALL", "WALLS", "A-WALL", "EXT_WALL", "INT_WALL", "PARTITION",
            "DINDING", "OUTER_WALL", "INNER_WALL",
        ],
        "door_layers": [
            "DOOR", "DOORS", "DR", "PINTU", "GATE", "SWING",
        ],
        "window_layers": [
            "WINDOW", "WIN", "CASEMENT", "JENDELA", "WDW", "VENTILATOR",
        ],
        "slab_layers": [
            "SLAB", "FLOOR", "TERRACE", "ROOF", "FOOTPRINT",
        ],
        "column_layers": [
            "COLUMN", "COL", "PILLAR", "PILLAR",
        ],
        "avoid_layers": [
            "TITLEBLOCK", "TITLE", "BORDER", "FRAME", "VIEWPORT",
            "DEFPOINTS", "REVISION", "LOGO",
        ],
        "tips": [
            "Place external and internal walls on separate named layers for best classification.",
            "Close all polylines that define room or building boundaries (use PEDIT → Close).",
            "Place door/window blocks on layers named DOOR or WINDOW.",
            "Set $INSUNITS correctly in AutoCAD: type UNITS → select Millimeters or Meters.",
            "If OLE2FRAME is detected: EXPLODE the OLE frame in AutoCAD, then Save As DXF 2010 ASCII.",
            "Layer '0' geometry is always included in area extraction.",
            "For best boundary detection use a single closed LWPOLYLINE for the outer building edge.",
            "Avoid putting dimensions, north arrows, and title blocks inside the model space.",
        ],
    }
