"""
DXF Upload API — v4
====================
POST /api/v1/dxf/upload/{project_id}
GET  /api/v1/dxf/layers-guide

Changes in v4
-------------
- Accepts .dxf only; .dwg rejected with clear AutoCAD conversion instructions
- Returns multi-building list (buildings[]) alongside primary footprint
- selected_boundary param lets user pick a different candidate
- apply_to_building writes slab_area_m2 (not W×H approximation)
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
    project_id:        UUID,
    file:              UploadFile = File(...),
    units:             str  = Form("mm"),
    apply_to_building: str  = Form("false"),
    selected_boundary: int  = Form(-1),   # 0-based index into boundary_candidates; -1 = auto
    db:          Session    = Depends(get_db),
    current_user: User      = Depends(get_current_active_user),
):
    """
    Parse an uploaded DXF file and return:
    - Out-to-out building footprint area (m² and ft²)
    - Multi-building breakdown (Building A, B, C …) when applicable
    - Boundary perimeter, wall lengths, door/window counts
    - Boundary candidates with SVG preview paths
    - Full diagnostics panel data
    """
    fname = (file.filename or "").lower().strip()

    # ── DWG → reject with instructions ───────────────────────────────────────
    if fname.endswith(".dwg"):
        raise HTTPException(
            status_code=415,
            detail=(
                "DWG binary files cannot be parsed directly. "
                "Convert to DXF first: in AutoCAD open the file → "
                "File → Save As → AutoCAD 2010 DXF (ASCII) → re-upload the .dxf file. "
                "Free converter: ODA File Converter — "
                "https://www.opendesign.com/guestfiles/oda_file_converter"
            ),
        )

    if not fname.endswith(".dxf"):
        raise HTTPException(
            status_code=400,
            detail="Only DXF files are accepted (.dxf extension required).",
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum {settings.MAX_FILE_SIZE_MB} MB.",
        )

    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # ── Parse ─────────────────────────────────────────────────────────────────
    result = parse_dxf_bytes(content, units=units)
    data   = result.to_dict()

    # ── User-selected boundary override ───────────────────────────────────────
    candidates = data.get("boundary_candidates", [])
    if 0 <= selected_boundary < len(candidates):
        chosen = candidates[selected_boundary]
        data["building_footprint_area_m2"]  = chosen["area_m2"]
        data["building_footprint_area_ft2"] = chosen["area_ft2"]
        data["boundary_perimeter_m"]        = chosen["perimeter_m"]
        data["boundary_perimeter_ft"]       = chosen["perimeter_ft"]
        data["slab_area_m2"]                = chosen["area_m2"]
        data["total_floor_area_m2"]         = chosen["area_m2"]
        for i, c in enumerate(candidates):
            c["is_selected"] = (i == selected_boundary)
        data["warnings"].append(
            f"User selected boundary #{selected_boundary + 1} "
            f"({chosen['area_m2']} m²)."
        )
        if "selected_boundary" in data.get("diagnostics", {}):
            data["diagnostics"]["selected_boundary"].update({
                "area_m2":      chosen["area_m2"],
                "perimeter_m":  chosen["perimeter_m"],
                "width_m":      chosen["width_m"],
                "height_m":     chosen["height_m"],
                "user_selected": True,
            })

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
                sel  = data.get("diagnostics", {}).get("selected_boundary", {})
                w    = sel.get("width_m", 0)
                h    = sel.get("height_m", 0)

                # Also check candidates list
                if not (w > 0 and h > 0):
                    for c in candidates:
                        if c.get("is_selected"):
                            w = c.get("width_m", 0)
                            h = c.get("height_m", 0)
                            break

                if w > 0 and h > 0:
                    upd["plot_length"] = round(w, 3)
                    upd["plot_width"]  = round(h, 3)
                    upd["slab_length"] = round(w, 3)
                    upd["slab_width"]  = round(h, 3)
                else:
                    side = round(footprint ** 0.5, 3)
                    upd["plot_length"] = side
                    upd["plot_width"]  = side
                    upd["slab_length"] = side
                    upd["slab_width"]  = side

            if data.get("external_wall_length_m", 0) > 0:
                upd["total_external_wall_length"] = round(data["external_wall_length_m"], 3)
            if data.get("internal_wall_length_m", 0) > 0:
                upd["total_internal_wall_length"] = round(data["internal_wall_length_m"], 3)
            if data["num_doors"]   > 0: upd["num_doors"]   = data["num_doors"]
            if data["num_windows"] > 0: upd["num_windows"] = data["num_windows"]

            if upd:
                building_crud.update_building(db, b, BuildingUpdate(**upd))
                applied = True
        else:
            data["warnings"].append(
                "No building found for this project. "
                "Create a building first, then re-upload with 'Extract & Apply'."
            )

    # ── Response ──────────────────────────────────────────────────────────────
    return {
        "project_id":          str(project_id),
        "filename":            file.filename,
        "file_size_kb":        round(len(content) / 1024, 1),
        "units_used":          data["units_used"],
        "units_detected":      data["units_detected"],
        "scale_factor":        data["scale_factor"],
        "applied_to_building": applied,

        "extracted": {
            # Primary BOQ values
            "building_footprint_area_m2":  data["building_footprint_area_m2"],
            "building_footprint_area_ft2": data["building_footprint_area_ft2"],
            "boundary_perimeter_m":        data["boundary_perimeter_m"],
            "boundary_perimeter_ft":       data["boundary_perimeter_ft"],
            "slab_area_m2":                data["slab_area_m2"],

            # Legacy keys
            "total_floor_area_m2":  data["building_footprint_area_m2"],
            "total_wall_length_m":  data["total_wall_length_m"],

            # Wall breakdown
            "external_wall_length_m": data["external_wall_length_m"],
            "internal_wall_length_m": data["internal_wall_length_m"],

            # Openings
            "num_doors":   data["num_doors"],
            "num_windows": data["num_windows"],

            # Multi-building list
            "buildings": data.get("buildings", []),

            # Sub-areas / rooms
            "rooms": data["rooms"],

            # Boundary candidates (with SVG paths)
            "boundary_candidates": data["boundary_candidates"],

            # Entity counts for diagnostics
            "entity_counts": data["entity_counts"],

            # SVG viewport
            "svg_viewbox": (
                data["boundary_candidates"][0].get("svg_viewbox", "0 0 480 320")
                if data["boundary_candidates"] else "0 0 480 320"
            ),
        },

        "diagnostics": data["diagnostics"],
        "warnings":    data["warnings"],
    }


@router.get("/layers-guide", summary="DXF layer naming conventions guide")
def layers_guide(_: User = Depends(get_current_active_user)):
    return {
        "wall_layers":   ["WALL","WALLS","A-WALL","EXT_WALL","INT_WALL","PARTITION"],
        "door_layers":   ["DOOR","DOORS","DR","PINTU","GATE","SWING"],
        "window_layers": ["WINDOW","WIN","CASEMENT","JENDELA","WDW"],
        "slab_layers":   ["SLAB","FLOOR","TERRACE","ROOF","FOOTPRINT"],
        "column_layers": ["COLUMN","COL","PILLAR"],
        "avoid_layers":  ["TITLEBLOCK","TITLE","BORDER","FRAME","VIEWPORT","DEFPOINTS"],
        "tips": [
            "For best results draw the outer building boundary as a single closed LWPOLYLINE.",
            "Set $INSUNITS in AutoCAD: type UNITS → set Millimeters, Meters, Feet etc.",
            "Place external and internal walls on separate named layers.",
            "Mark door/window blocks on layers named DOOR or WINDOW.",
            "If OLE2FRAME is detected: EXPLODE in AutoCAD → Save As DXF 2010 ASCII.",
            "DWG files must be converted to DXF: File → Save As → AutoCAD 2010 DXF.",
            "Layer '0' geometry is always included.",
        ],
    }
