from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
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


@router.post("/upload/{project_id}", summary="Upload DXF file and extract building dimensions")
async def upload_dxf(
    project_id: UUID,
    file: UploadFile = File(..., description="AutoCAD DXF file"),
    units: str = Form("mm", description="Drawing units: mm, cm, m, ft, in"),
    apply_to_building: bool = Form(False, description="Auto-update the project's first building"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Parse an uploaded DXF file and return extracted dimensions.

    - Extracts wall lengths (from LINE/LWPOLYLINE on WALL layers)
    - Extracts floor area (from closed LWPOLYLINE on ROOM/FLOOR layers)
    - Counts doors and windows (from INSERT blocks on DOOR/WINDOW layers)

    If `apply_to_building=true`, updates the project's first building record
    with the extracted dimensions automatically.
    """
    # Validate file type — accept .dxf only (not .dwg which is binary proprietary)
    fname = file.filename.lower()
    if not fname.endswith(".dxf"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only DXF files are accepted. "
                "If you have a DWG file, open it in AutoCAD and save as: "
                "File → Save As → DXF 2010 (ASCII format)."
            ),
        )

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB")

    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Parse
    result = parse_dxf_bytes(content, units=units)
    data   = result.to_dict()

    # Optionally apply extracted data to building
    applied = False
    if apply_to_building:
        buildings = building_crud.get_buildings_by_project(db, project_id)
        if buildings:
            b = buildings[0]
            update_payload = BuildingUpdate(
                total_external_wall_length=round(data["total_wall_length_m"] * 0.6, 2),
                total_internal_wall_length=round(data["total_wall_length_m"] * 0.4, 2),
                num_doors=data["num_doors"],
                num_windows=data["num_windows"],
            )
            # Derive plot from floor area if available
            if data["total_floor_area_m2"] > 0:
                side = round(data["total_floor_area_m2"] ** 0.5, 2)
                update_payload.plot_length = side
                update_payload.plot_width  = side
                update_payload.slab_length = side
                update_payload.slab_width  = side

            building_crud.update_building(db, b, update_payload)
            applied = True
        else:
            data["warnings"].append(
                "No building found for this project. Create a building first, then apply DXF data."
            )

    return {
        "project_id":     str(project_id),
        "filename":       file.filename,
        "units_used":     units,
        "scale_factor":   data["scale_factor"],
        "extracted": {
            "total_wall_length_m": data["total_wall_length_m"],
            "total_floor_area_m2": data["total_floor_area_m2"],
            "num_doors":           data["num_doors"],
            "num_windows":         data["num_windows"],
            "rooms":               data["rooms"],
            "entity_counts":       data["entity_counts"],
        },
        "applied_to_building": applied,
        "warnings":        data["warnings"],
    }


@router.get("/layers-guide", summary="Guide to DXF layer naming conventions")
def layers_guide(_: User = Depends(get_current_active_user)):
    """Returns the expected DXF layer naming guide for correct extraction."""
    return {
        "wall_layers":    ["WALL", "WALLS", "EXT_WALL", "INT_WALL", "PARTITION", "DINDING"],
        "door_layers":    ["DOOR", "DOORS", "PINTU"],
        "window_layers":  ["WINDOW", "WINDOWS", "JENDELA"],
        "room_layers":    ["ROOM", "ROOMS", "FLOOR", "AREA", "HATCH"],
        "tips": [
            "Draw external and internal walls on separate layers for best results.",
            "Rooms should be closed LWPOLYLINE entities.",
            "Doors and windows can be INSERT (block references) on their respective layers.",
            "Set DXF units to match the 'units' parameter when uploading (default: mm).",
        ],
    }
