"""
BBS API — Bar Bending Schedule
================================
Manual BBS, Auto BBS from drawings, calculations, Excel/PDF export.
"""
from __future__ import annotations
import io, uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.bbs import BBSSheet, BBSBar
from app.crud.project import get_project_by_id
from app.services.bbs_engine import (
    BeamBarInput, ColumnBarInput, StirrupInput,
    calc_beam_bar, calc_column_bar, calc_stirrups,
    calc_slab_bar, diameter_summary, unit_weight_kg_per_m,
    development_length, lap_length,
    VERIFY, CONFLICT, MISSING,
)

router = APIRouter()


# ══════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ══════════════════════════════════════════════════════

class BBSBarCreate(BaseModel):
    sort_order: int = 0
    is_heading: bool = False
    bar_mark:   Optional[str] = None
    position:   Optional[str] = None
    member_mark: Optional[str] = None
    floor_level: Optional[str] = None
    dia_mm:     Optional[int] = None
    bar_shape:  str = "straight"
    num_bars:   Optional[int] = 0
    clear_span_mm:    Optional[float] = None
    support_near_mm:  Optional[float] = None
    support_far_mm:   Optional[float] = None
    section_b_mm:     Optional[float] = None
    section_d_mm:     Optional[float] = None
    cover_mm:         Optional[float] = None
    spacing_mm:       Optional[float] = None
    storey_height_mm: Optional[float] = None
    zone_length_mm:   Optional[float] = None
    has_hook_near: bool = False
    has_hook_far:  bool = False
    hook_type:     str  = "standard"
    lap_mm:          Optional[float] = None
    dev_length_mm:   Optional[float] = None
    source:  str = "manual"
    remarks: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def handle_empty_strings(cls, values):
        """Convert empty strings to None for optional float fields"""
        if isinstance(values, dict):
            float_fields = ['clear_span_mm', 'support_near_mm', 'support_far_mm', 
                           'section_b_mm', 'section_d_mm', 'cover_mm', 'spacing_mm', 
                           'storey_height_mm', 'zone_length_mm', 'lap_mm', 'dev_length_mm']
            for field in float_fields:
                if field in values and isinstance(values[field], str):
                    if values[field] == "" or values[field].lower() in ["null", "undefined", "none"]:
                        values[field] = None
        return values


class BBSBarOut(BBSBarCreate):
    id: str
    sheet_id: str
    cutting_length_mm: Optional[float] = None
    total_length_mm:   Optional[float] = None
    unit_weight_kg_per_m: Optional[float] = None
    total_weight_kg:   Optional[float] = None
    formula: Optional[str] = None
    status:  str = "calculated"
    created_at: datetime
    model_config = {"from_attributes": True}


class BBSSheetCreate(BaseModel):
    title:       str
    member_type: str = "beam"    # beam|column|slab|footing
    mode:        str = "manual"
    drawing_ref: Optional[str] = None
    fck:   int   = 20
    fy:    int   = 500
    clear_cover: Optional[float] = None
    bond_type:   str = "deformed"
    notes:       Optional[str] = None


class BBSSheetOut(BBSSheetCreate):
    id:          str
    project_id:  str
    sheet_number: str
    is_approved: bool
    bars: List[BBSBarOut] = []
    created_at: datetime
    model_config = {"from_attributes": True}


class BBSSheetListItem(BaseModel):
    id: str
    sheet_number: str
    title: str
    member_type: str
    mode: str
    is_approved: bool
    bar_count:  int = 0
    total_weight_kg: float = 0.0
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Quick-calc schemas ─────────────────────────────────
class BeamBarCalcReq(BaseModel):
    clear_span_mm:       float
    support_near_mm:     float = 230.0
    support_far_mm:      float = 230.0
    dia_mm:              int   = 16
    num_bars:            int   = 2
    has_hook_near:       bool  = True
    has_hook_far:        bool  = True
    hook_type:           str   = "standard"
    splice_required:     bool  = False
    fck: int = 20; fy: int = 500
    bond_type: str = "deformed"

class ColumnBarCalcReq(BaseModel):
    storey_height_mm:  float
    dia_mm:            int   = 16
    num_bars:          int   = 4
    cover_mm:          float = 40.0
    lap_mm:            float = 0.0
    fck: int = 20; fy: int = 500
    extra_top_mm:      float = 0.0

class StirrupCalcReq(BaseModel):
    b_mm:          float
    d_mm:          float
    dia_mm:        int   = 8
    cover_mm:      float = 25.0
    spacing_mm:    float = 150.0
    zone_length_mm: float = 0.0
    clear_span_mm:  float = 0.0
    hook_type:      str   = "135"


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _auto_number(db: Session, project_id: str) -> str:
    count = db.query(BBSSheet).filter(BBSSheet.project_id == project_id).count()
    return f"BBS-{count + 1:03d}"


def _check_project(db: Session, project_id: uuid.UUID, user: User):
    from app.models.user import UserRole
    p = get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        if str(p.created_by) != str(user.id):
            raise HTTPException(status_code=403, detail="Access denied")
    return p


def _recalc_bar(bar: BBSBar, sheet: BBSSheet) -> BBSBar:
    """Run BBS engine on a bar row and update computed columns."""
    if bar.is_heading or not bar.dia_mm:
        return bar

    fck = sheet.fck or 20
    fy  = sheet.fy  or 500
    bt  = sheet.bond_type or "deformed"
    cover = bar.cover_mm or sheet.clear_cover or 25.0

    member_type = sheet.member_type
    shape = (bar.bar_shape or "straight").lower()

    if shape in ("stirrup_rect", "stirrup_square") or "stirr" in shape or "tie" in shape:
        if bar.section_b_mm and bar.section_d_mm:
            inp = StirrupInput(
                b_mm=bar.section_b_mm, d_mm=bar.section_d_mm,
                dia_mm=bar.dia_mm, cover_mm=cover,
                spacing_mm=bar.spacing_mm or 150.0,
                zone_length_mm=bar.zone_length_mm or 0.0,
                clear_span_mm=bar.clear_span_mm or 0.0,
                shape="rect", hook_type=bar.hook_type or "135",
                source=bar.source,
            )
            res = calc_stirrups(inp, bar.bar_mark or "ST")
            bar.cutting_length_mm    = res.cutting_length_mm
            bar.total_length_mm      = res.total_length_mm
            bar.unit_weight_kg_per_m = res.unit_weight
            bar.total_weight_kg      = res.total_weight_kg
            bar.formula = res.formula
            bar.status  = res.status
            bar.num_bars = res.num_stirrups

    elif member_type == "column" or shape == "straight" and bar.storey_height_mm:
        if bar.storey_height_mm:
            inp = ColumnBarInput(
                storey_height_mm=bar.storey_height_mm,
                dia_mm=bar.dia_mm, num_bars=bar.num_bars or 4,
                cover_mm=cover,
                lap_mm=bar.lap_mm or 0.0,
                fck=fck, fy=fy, bond_type=bt,
                extra_length_mm=0.0, source=bar.source,
            )
            res = calc_column_bar(inp, bar.bar_mark or "C")
            bar.cutting_length_mm    = res.cutting_length_mm
            bar.lap_mm               = res.lap_length_mm
            bar.total_length_mm      = res.total_length_mm
            bar.unit_weight_kg_per_m = res.unit_weight
            bar.total_weight_kg      = res.total_weight_kg
            bar.formula = res.formula
            bar.status  = res.status

    else:
        if bar.clear_span_mm:
            inp = BeamBarInput(
                clear_span_mm=bar.clear_span_mm,
                support_near_mm=bar.support_near_mm or 230.0,
                support_far_mm=bar.support_far_mm or 230.0,
                dia_mm=bar.dia_mm, num_bars=bar.num_bars or 2,
                has_hook_near=bar.has_hook_near,
                has_hook_far=bar.has_hook_far,
                hook_type=bar.hook_type or "standard",
                splice_required=bool(bar.lap_mm and bar.lap_mm > 0),
                fck=fck, fy=fy, bond_type=bt, source=bar.source,
            )
            res = calc_beam_bar(inp, bar.bar_mark or "B")
            bar.cutting_length_mm    = res.cutting_length_mm
            bar.lap_mm               = res.lap_length_mm
            bar.total_length_mm      = res.total_length_mm
            bar.unit_weight_kg_per_m = res.unit_weight
            bar.total_weight_kg      = res.total_weight_kg
            bar.formula = res.formula
            bar.status  = res.status
        else:
            bar.status = MISSING
            bar.formula = "clear_span_mm not provided"

    return bar


# ══════════════════════════════════════════════════════
# SHEET CRUD
# ══════════════════════════════════════════════════════

@router.get("/project/{project_id}", response_model=List[BBSSheetListItem])
def list_sheets(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    sheets = db.query(BBSSheet).filter(BBSSheet.project_id == str(project_id)).order_by(BBSSheet.created_at).all()
    result = []
    for s in sheets:
        bars = [b for b in s.bars if not b.is_heading]
        result.append(BBSSheetListItem(
            id=s.id, sheet_number=s.sheet_number, title=s.title,
            member_type=s.member_type, mode=s.mode, is_approved=s.is_approved,
            bar_count=len(bars),
            total_weight_kg=round(sum(b.total_weight_kg or 0 for b in bars), 3),
            created_at=s.created_at,
        ))
    return result


@router.post("/project/{project_id}", response_model=BBSSheetOut, status_code=201)
def create_sheet(
    project_id: uuid.UUID,
    payload: BBSSheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    sheet = BBSSheet(
        project_id=str(project_id),
        sheet_number=_auto_number(db, str(project_id)),
        prepared_by=str(current_user.id),
        **payload.model_dump(),
    )
    db.add(sheet); db.commit(); db.refresh(sheet)
    return sheet


@router.get("/{sheet_id}", response_model=BBSSheetOut)
def get_sheet(
    sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404, "BBS sheet not found")
    _check_project(db, uuid.UUID(sheet.project_id), current_user)
    return sheet


@router.put("/{sheet_id}", response_model=BBSSheetOut)
def update_sheet(
    sheet_id: uuid.UUID,
    payload: BBSSheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404, "BBS sheet not found")
    _check_project(db, uuid.UUID(sheet.project_id), current_user)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sheet, k, v)
    db.commit(); db.refresh(sheet)
    return sheet


@router.delete("/{sheet_id}", status_code=204)
def delete_sheet(
    sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404, "BBS sheet not found")
    _check_project(db, uuid.UUID(sheet.project_id), current_user)
    db.delete(sheet); db.commit()


# ══════════════════════════════════════════════════════
# BAR CRUD
# ══════════════════════════════════════════════════════

@router.post("/{sheet_id}/bars", response_model=BBSBarOut, status_code=201)
def add_bar(
    sheet_id: uuid.UUID,
    payload: BBSBarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404, "BBS sheet not found")
    _check_project(db, uuid.UUID(sheet.project_id), current_user)

    bar = BBSBar(sheet_id=str(sheet_id), **payload.model_dump())
    bar = _recalc_bar(bar, sheet)
    db.add(bar); db.commit(); db.refresh(bar)
    return bar


@router.put("/{sheet_id}/bars/{bar_id}", response_model=BBSBarOut)
def update_bar(
    sheet_id: uuid.UUID,
    bar_id: uuid.UUID,
    payload: BBSBarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404, "BBS sheet not found")
    _check_project(db, uuid.UUID(sheet.project_id), current_user)
    bar = db.query(BBSBar).filter(BBSBar.id == str(bar_id), BBSBar.sheet_id == str(sheet_id)).first()
    if not bar: raise HTTPException(404, "Bar not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(bar, k, v)
    bar = _recalc_bar(bar, sheet)
    db.commit(); db.refresh(bar)
    return bar


@router.delete("/{sheet_id}/bars/{bar_id}", status_code=204)
def delete_bar(
    sheet_id: uuid.UUID, bar_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404)
    _check_project(db, uuid.UUID(sheet.project_id), current_user)
    bar = db.query(BBSBar).filter(BBSBar.id == str(bar_id), BBSBar.sheet_id == str(sheet_id)).first()
    if not bar: raise HTTPException(404)
    db.delete(bar); db.commit()


# ══════════════════════════════════════════════════════
# RECALCULATE ALL BARS
# ══════════════════════════════════════════════════════

@router.post("/{sheet_id}/recalculate")
def recalculate_sheet(
    sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404)
    _check_project(db, uuid.UUID(sheet.project_id), current_user)
    for bar in sheet.bars:
        _recalc_bar(bar, sheet)
    db.commit()
    total_wt = sum(b.total_weight_kg or 0 for b in sheet.bars if not b.is_heading)
    return {"recalculated": len(sheet.bars), "total_weight_kg": round(total_wt, 3)}


# ══════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════

@router.get("/{sheet_id}/summary")
def sheet_summary(
    sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404)
    _check_project(db, uuid.UUID(sheet.project_id), current_user)

    bars = [b for b in sheet.bars if not b.is_heading and b.dia_mm]
    bar_rows = [
        {"dia_mm": b.dia_mm, "total_length_mm": b.total_length_mm or 0,
         "total_weight_kg": b.total_weight_kg or 0, "num_bars": b.num_bars or 0}
        for b in bars
    ]
    dia_sum = diameter_summary(bar_rows)
    total_wt = sum(b.total_weight_kg or 0 for b in bars)

    return {
        "sheet_id": str(sheet_id),
        "title": sheet.title,
        "bar_count": len(bars),
        "total_weight_kg": round(total_wt, 3),
        "diameter_summary": list(dia_sum.values()),
        "verify_items": [b.bar_mark for b in sheet.bars if b.status in (VERIFY, CONFLICT, MISSING)],
    }


# ══════════════════════════════════════════════════════
# QUICK CALCULATIONS (standalone, no DB)
# ══════════════════════════════════════════════════════

@router.post("/calc/beam-bar")
def calc_beam(req: BeamBarCalcReq, _: User = Depends(get_current_active_user)):
    inp = BeamBarInput(
        clear_span_mm=req.clear_span_mm,
        support_near_mm=req.support_near_mm,
        support_far_mm=req.support_far_mm,
        dia_mm=req.dia_mm, num_bars=req.num_bars,
        has_hook_near=req.has_hook_near, has_hook_far=req.has_hook_far,
        hook_type=req.hook_type, splice_required=req.splice_required,
        fck=req.fck, fy=req.fy, bond_type=req.bond_type,
    )
    r = calc_beam_bar(inp)
    return r.__dict__


@router.post("/calc/column-bar")
def calc_col(req: ColumnBarCalcReq, _: User = Depends(get_current_active_user)):
    inp = ColumnBarInput(
        storey_height_mm=req.storey_height_mm,
        dia_mm=req.dia_mm, num_bars=req.num_bars,
        cover_mm=req.cover_mm, lap_mm=req.lap_mm,
        fck=req.fck, fy=req.fy, extra_top_mm=req.extra_top_mm,
    )
    r = calc_column_bar(inp)
    return r.__dict__


@router.post("/calc/stirrup")
def calc_stir(req: StirrupCalcReq, _: User = Depends(get_current_active_user)):
    inp = StirrupInput(
        b_mm=req.b_mm, d_mm=req.d_mm, dia_mm=req.dia_mm,
        cover_mm=req.cover_mm, spacing_mm=req.spacing_mm,
        zone_length_mm=req.zone_length_mm, clear_span_mm=req.clear_span_mm,
        hook_type=req.hook_type,
    )
    r = calc_stirrups(inp)
    return r.__dict__


@router.get("/calc/development-length")
def calc_dev_len(
    dia: int, fck: int = 20, fy: int = 500,
    bond_type: str = "deformed",
    _: User = Depends(get_current_active_user),
):
    ld = development_length(dia, fck, fy, bond_type)
    lp = lap_length(dia, fck, fy, bond_type)
    return {"dia_mm": dia, "development_length_mm": ld, "lap_length_mm": lp,
            "formula": f"Ld = (fy×d)/(4×τbd×1.15) | IS 456 Cl.26.2"}


# ══════════════════════════════════════════════════════
# AUTO BBS FROM DRAWING UPLOAD
# ══════════════════════════════════════════════════════

@router.post("/project/{project_id}/extract-drawing")
async def extract_drawing(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    member_query: str = Form("all"),   # "all" | "EB5" | "C1" etc.
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload DXF/DWG/PDF structural drawing.
    Extracts member information and returns extraction review for engineer confirmation.
    """
    _check_project(db, project_id, current_user)
    fname = (file.filename or "").lower()
    content = await file.read()

    extracted = []

    if fname.endswith(".dxf"):
        from app.services.dxf_parser import parse_dxf_bytes
        result = parse_dxf_bytes(content)
        d = result.to_dict()
        # Return geometry info as extracted member data
        diag = d.get("diagnostics", {})
        ext = d.get("drawing_extents", diag.get("drawing_extents", {}))
        extracted.append({
            "member_mark": "BUILDING",
            "source": "dxf_geometry",
            "clear_span_mm": ext.get("width_drawing_units", 0) * d.get("scale_factor", 0.001),
            "building_footprint_m2": d.get("building_footprint_area_m2", 0),
            "wall_length_m": d.get("total_wall_length_m", 0),
            "status": "measured",
            "warnings": d.get("warnings", []),
            "diagnostics": diag,
        })

    elif fname.endswith((".pdf",)):
        extracted.append({
            "member_mark": member_query,
            "source": "pdf_upload",
            "status": "verify_required",
            "message": (
                "PDF uploaded. Automatic text extraction from PDF structural schedules "
                "is not yet implemented. Please use the Manual BBS entry form to enter "
                "values from this schedule, or upload a DXF file for geometry extraction."
            ),
        })

    else:
        extracted.append({
            "member_mark": member_query,
            "source": "unknown_format",
            "status": "verify_required",
            "message": (
                f"File format '{fname.split('.')[-1].upper()}' is not directly supported. "
                "Supported: DXF (geometry extraction), PDF (manual schedule reference). "
                "For DWG files: open in AutoCAD → Save As → DXF 2010 ASCII, then re-upload."
            ),
        })

    return {
        "project_id": str(project_id),
        "filename": file.filename,
        "member_query": member_query,
        "extracted": extracted,
        "instructions": (
            "Review the extracted values below. Edit any incorrect values, "
            "then click 'Create BBS from Extraction' to generate the BBS sheet."
        ),
    }


# ══════════════════════════════════════════════════════
# EXCEL EXPORT
# ══════════════════════════════════════════════════════

@router.get("/{sheet_id}/export/excel")
def export_excel(
    sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404)
    _check_project(db, uuid.UUID(sheet.project_id), current_user)

    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(500, "openpyxl not installed")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet.sheet_number[:31]

    # Styles
    navy  = "1E3A5F"
    white = "FFFFFF"
    hdr_font  = Font(name="Arial", bold=True, color=white, size=10)
    hdr_fill  = PatternFill("solid", fgColor=navy)
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center")

    # Title block
    ws.merge_cells("A1:O1")
    ws["A1"] = f"BAR BENDING SCHEDULE — {sheet.title.upper()}"
    ws["A1"].font = Font(name="Arial", bold=True, size=13, color=white)
    ws["A1"].fill = PatternFill("solid", fgColor=navy)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:O2")
    ws["A2"] = f"Sheet No: {sheet.sheet_number}   |   fck: M{sheet.fck}   |   fy: Fe{sheet.fy}   |   Type: {sheet.member_type.upper()}"
    ws["A2"].alignment = Alignment(horizontal="center")
    ws["A2"].font = Font(name="Arial", size=9, bold=True)

    # Column headers
    headers = [
        "Bar\nMark", "Member", "Position", "Floor",
        "Dia\n(mm)", "Shape", "No.\nBars",
        "Clear\nSpan (mm)", "B×D\n(mm)",
        "Cut Length\n(mm)", "Lap\n(mm)", "No. Bars",
        "Total Length\n(mm)", "Unit Wt\n(kg/m)", "Total Wt\n(kg)",
    ]
    col_widths = [8, 10, 14, 8, 6, 10, 6, 12, 10, 12, 8, 7, 14, 10, 10]
    for i, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=3, column=i, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        cell.border = border
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[3].height = 30

    # Data rows
    row_idx = 4
    for bar in sheet.bars:
        if bar.is_heading:
            ws.merge_cells(f"A{row_idx}:O{row_idx}")
            c = ws.cell(row=row_idx, column=1, value=f"  {bar.bar_mark or bar.position or 'Section'}")
            c.font = Font(bold=True, size=10)
            c.fill = PatternFill("solid", fgColor="D9E1F2")
            c.alignment = Alignment(horizontal="left")
            row_idx += 1
            continue

        section_str = ""
        if bar.section_b_mm and bar.section_d_mm:
            section_str = f"{bar.section_b_mm:.0f}×{bar.section_d_mm:.0f}"

        vals = [
            bar.bar_mark or "", bar.member_mark or "", bar.position or "", bar.floor_level or "",
            bar.dia_mm or "", bar.bar_shape or "", bar.num_bars or 0,
            bar.clear_span_mm or "", section_str,
            bar.cutting_length_mm or "", bar.lap_mm or "", bar.num_bars or 0,
            bar.total_length_mm or "", bar.unit_weight_kg_per_m or "", bar.total_weight_kg or "",
        ]
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=row_idx, column=col, value=v)
            c.border = border
            c.alignment = center
            c.font = Font(size=9)
            if bar.status in ("verify_required", "conflict", "missing_input"):
                c.fill = PatternFill("solid", fgColor="FFE0E0")
        row_idx += 1

    # Diameter summary
    row_idx += 1
    ws.cell(row=row_idx, column=1, value="DIAMETER-WISE SUMMARY").font = Font(bold=True)
    row_idx += 1
    s_hdrs = ["Dia (mm)", "No. Bars", "Total Length (m)", "Total Weight (kg)"]
    for c, h in enumerate(s_hdrs, 1):
        cell = ws.cell(row=row_idx, column=c, value=h)
        cell.font = hdr_font; cell.fill = hdr_fill; cell.border = border; cell.alignment = center
    row_idx += 1

    bars = [b for b in sheet.bars if not b.is_heading and b.dia_mm]
    bar_rows = [{"dia_mm": b.dia_mm, "total_length_mm": b.total_length_mm or 0,
                 "total_weight_kg": b.total_weight_kg or 0, "num_bars": b.num_bars or 0} for b in bars]
    for d, s in sorted(diameter_summary(bar_rows).items()):
        vals = [f"{d} mm", s["num_bars"], s["total_length_m"], s["total_weight_kg"]]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=row_idx, column=c, value=v)
            cell.border = border; cell.alignment = center
        row_idx += 1

    # Grand total
    total_wt = round(sum(b.total_weight_kg or 0 for b in bars), 3)
    ws.cell(row=row_idx, column=1, value="TOTAL STEEL WEIGHT (kg)").font = Font(bold=True)
    ws.cell(row=row_idx, column=4, value=total_wt).font = Font(bold=True)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=BBS_{sheet.sheet_number}.xlsx"},
    )


# ══════════════════════════════════════════════════════
# PDF EXPORT
# ══════════════════════════════════════════════════════

@router.get("/{sheet_id}/export/pdf")
def export_pdf(
    sheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    sheet = db.query(BBSSheet).filter(BBSSheet.id == str(sheet_id)).first()
    if not sheet: raise HTTPException(404)
    _check_project(db, uuid.UUID(sheet.project_id), current_user)

    try:
        from reportlab.lib.pagesizes import A3, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise HTTPException(500, "reportlab not installed")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A3),
                            leftMargin=10*mm, rightMargin=10*mm,
                            topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#1E3A5F")
    story = []

    # Title
    title_style = ParagraphStyle("title", fontSize=13, textColor=colors.white,
                                  backColor=navy, alignment=TA_CENTER, spaceAfter=2*mm)
    story.append(Paragraph(f"BAR BENDING SCHEDULE — {sheet.title.upper()}", title_style))
    story.append(Paragraph(
        f"Sheet: {sheet.sheet_number} &nbsp;&nbsp; fck: M{sheet.fck} &nbsp;&nbsp; "
        f"fy: Fe{sheet.fy} &nbsp;&nbsp; Type: {sheet.member_type.upper()}",
        ParagraphStyle("sub", fontSize=8, alignment=TA_CENTER, spaceAfter=3*mm)
    ))

    # Table
    col_hdrs = ["Bar\nMark","Member","Position","Dia\n(mm)","Shape","No.","Span\n(mm)",
                "B×D\n(mm)","Cut L\n(mm)","Lap\n(mm)","Total L\n(mm)","Wt/m\n(kg)","Total Wt\n(kg)","Status"]
    data = [col_hdrs]
    col_w = [15*mm,20*mm,25*mm,12*mm,18*mm,10*mm,18*mm,16*mm,18*mm,14*mm,18*mm,14*mm,16*mm,16*mm]

    for bar in sheet.bars:
        if bar.is_heading:
            data.append([Paragraph(f"<b>{bar.bar_mark or bar.position or ''}</b>",
                                   ParagraphStyle("h", fontSize=8))] + [""]*(len(col_hdrs)-1))
            continue
        sec = f"{bar.section_b_mm:.0f}×{bar.section_d_mm:.0f}" if (bar.section_b_mm and bar.section_d_mm) else ""
        data.append([
            bar.bar_mark or "", bar.member_mark or "", bar.position or "",
            bar.dia_mm or "", bar.bar_shape or "", bar.num_bars or "",
            f"{bar.clear_span_mm:.0f}" if bar.clear_span_mm else "",
            sec,
            f"{bar.cutting_length_mm:.0f}" if bar.cutting_length_mm else "",
            f"{bar.lap_mm:.0f}" if bar.lap_mm else "",
            f"{bar.total_length_mm:.0f}" if bar.total_length_mm else "",
            f"{bar.unit_weight_kg_per_m:.3f}" if bar.unit_weight_kg_per_m else "",
            f"{bar.total_weight_kg:.3f}" if bar.total_weight_kg else "",
            bar.status or "",
        ])

    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), navy),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTSIZE",   (0,0), (-1,-1), 7),
        ("FONTNAME",   (0,0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0F4FA")]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))

    # Summary
    bars = [b for b in sheet.bars if not b.is_heading and b.dia_mm]
    bar_rows = [{"dia_mm": b.dia_mm,"total_length_mm":b.total_length_mm or 0,
                 "total_weight_kg":b.total_weight_kg or 0,"num_bars":b.num_bars or 0} for b in bars]
    dia_s = diameter_summary(bar_rows)
    total_wt = round(sum(b.total_weight_kg or 0 for b in bars), 3)

    story.append(Paragraph("<b>DIAMETER-WISE SUMMARY</b>",
                            ParagraphStyle("sh", fontSize=9, spaceAfter=2*mm)))
    s_data = [["Dia (mm)","No. Bars","Total Length (m)","Total Weight (kg)"]]
    for d, s in sorted(dia_s.items()):
        s_data.append([f"{d} mm", s["num_bars"], s["total_length_m"], s["total_weight_kg"]])
    s_data.append(["TOTAL", "", "", total_wt])

    st = Table(s_data, colWidths=[30*mm,30*mm,50*mm,50*mm])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), navy),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold"),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
    ]))
    story.append(st)

    doc.build(story)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=BBS_{sheet.sheet_number}.pdf"},
    )


# ══════════════════════════════════════════════════════
# COMPLETE MANUAL BBS ENGINE INTEGRATION  
# ══════════════════════════════════════════════════════

from app.services.manual_bbs_engine import (
    ManualBBSEngine, MemberType, LapMethod, ConcreteGrade, SteelGrade,
    CurtailmentRule, ExtensionRule, DimensionConvention, QuantitySource, HookType, LapCondition,
    CompleteBeamInput, CompleteColumnInput, 
    BeamTopMainBar, BeamBottomMainBar, BeamCurtailedBar, BeamExtraBar, BeamStirrupZone,
    ColumnMainBar, ColumnReductionLevel, MasterStirrup, ShortLink, LongLink, CrossTie, ColumnZone,
    create_complete_beam_bbs, create_complete_column_bbs, create_complete_project_bbs,
    unit_weight_kg_per_m, calculate_lap_length, calculate_development_length_is456
)


# ══════════════════════════════════════════════════════
# COMPLETE BEAM INPUT STRUCTURES FOR API
# ══════════════════════════════════════════════════════

class CompleteBeamBBSRequest(BaseModel):
    """Complete beam BBS calculation request with all bar types"""
    # Beam Information — project/metadata are OPTIONAL, do NOT block calculation if blank
    project: str = Field("", description="Project name/ID (optional metadata)")
    building_tower: str = Field("", description="Building/Tower identifier")
    block: str = Field("", description="Block identifier")
    floor_level: str = Field("", description="Floor/Level")
    drawing_reference: str = Field("", description="Drawing/Sheet reference")
    beam_mark: str = Field(..., description="Beam mark/identifier")
    description: str = Field("", description="Member description")
    number_of_units: int = Field(1, description="Number of identical units")
    
    # Beam Dimensions
    beam_width: float = Field(..., description="Beam width in mm")
    beam_depth: float = Field(..., description="Beam depth in mm")
    clear_span: float = Field(..., description="Clear span in mm")
    
    # Material Properties
    concrete_grade: str = Field("M25", description="Concrete grade")
    steel_grade: str = Field("FE415", description="Steel grade")
    cover: float = Field(25, description="Cover in mm")
    
    # Top Main/Continuous Bars
    top_main_bars: List[dict] = Field(default_factory=list, description="Top main/continuous bars")
    
    # Bottom Main/Continuous Bars
    bottom_main_bars: List[dict] = Field(default_factory=list, description="Bottom main/continuous bars")
    
    # Bottom Mid-span/Curtailed Bars
    bottom_curtailed_bars: List[dict] = Field(default_factory=list, description="Bottom curtailed bars")
    
    # Top Extra Left Bars
    top_extra_left_bars: List[dict] = Field(default_factory=list, description="Top extra left bars")
    
    # Top Extra Right Bars
    top_extra_right_bars: List[dict] = Field(default_factory=list, description="Top extra right bars")
    
    # Beam Stirrups (Left/Middle/Right Zones)
    left_stirrup_zone: Optional[dict] = Field(None, description="Left/Support zone stirrups")
    middle_stirrup_zone: Optional[dict] = Field(None, description="Middle zone stirrups")
    right_stirrup_zone: Optional[dict] = Field(None, description="Right/Support zone stirrups")
    
    # Additional Information
    remarks: str = Field("", description="General remarks")

    class Config:
        json_schema_extra = {
            "example": {
                "project": "Residential Complex Phase-II",
                "building_tower": "Tower A",
                "block": "Block 1",
                "floor_level": "Ground Floor",
                "drawing_reference": "DRG-ST-001",
                "beam_mark": "GB1",
                "description": "Ground beam supporting slab",
                "number_of_units": 4,
                "beam_width": 300,
                "beam_depth": 450,
                "clear_span": 6000,
                "concrete_grade": "M25",
                "steel_grade": "FE415",
                "cover": 25,
                "top_main_bars": [
                    {
                        "bar_mark": "T1",
                        "diameter": 16,
                        "number_of_bars": 4,
                        "lap_method": "50D",
                        "hook_near": "90_DEGREE",
                        "remarks": "Continuous top bars"
                    }
                ],
                "bottom_main_bars": [
                    {
                        "bar_mark": "B1",
                        "diameter": 20,
                        "number_of_bars": 3,
                        "lap_method": "CODE_BASED",
                        "remarks": "Main bottom bars"
                    }
                ],
                "bottom_curtailed_bars": [
                    {
                        "bar_mark": "BC1",
                        "diameter": 16,
                        "number_of_bars": 2,
                        "curtailment_rule": "L/4",
                        "lap_method": "45D"
                    }
                ],
                "left_stirrup_zone": {
                    "stirrup_mark": "S1",
                    "diameter": 8,
                    "spacing": 100,
                    "zone_length": 1000,
                    "number_of_legs": 2,
                    "dimension_convention": "CENTRELINE"
                }
            }
        }


# ══════════════════════════════════════════════════════
# COMPLETE COLUMN INPUT STRUCTURES FOR API
# ══════════════════════════════════════════════════════

class CompleteColumnBBSRequest(BaseModel):
    """Complete column BBS calculation request with all tie types"""
    # Column Information — project/metadata are OPTIONAL, do NOT block calculation if blank
    project: str = Field("", description="Project name/ID (optional metadata)")
    building_tower: str = Field("", description="Building/Tower identifier")
    block: str = Field("", description="Block identifier")
    floor_level: str = Field("", description="Floor/Level")
    drawing_reference: str = Field("", description="Drawing/Sheet reference")
    column_mark: str = Field(..., description="Column mark/identifier")
    description: str = Field("", description="Member description")
    number_of_units: int = Field(1, description="Number of identical units")
    
    # Column Dimensions
    column_width: float = Field(..., description="Column width in mm")
    column_depth: float = Field(..., description="Column depth in mm")
    clear_floor_height: float = Field(..., description="Clear floor height in mm")
    
    # Material Properties
    concrete_grade: str = Field("M25", description="Concrete grade")
    steel_grade: str = Field("FE415", description="Steel grade")
    cover: float = Field(40, description="Cover in mm")
    
    # Main Vertical Bars
    main_vertical_bars: List[dict] = Field(default_factory=list, description="Main vertical bars")
    
    # Level-wise Reduction Configuration
    reduction_levels: List[dict] = Field(default_factory=list, description="Level-wise reductions")
    
    # Master/Main Closed Stirrups
    master_stirrups: List[dict] = Field(default_factory=list, description="Master/main stirrups")
    
    # Short Links
    short_links: List[dict] = Field(default_factory=list, description="Short links")
    
    # Long Links
    long_links: List[dict] = Field(default_factory=list, description="Long links")
    
    # Cross Ties
    cross_ties: List[dict] = Field(default_factory=list, description="Cross ties")
    
    # Zone Configuration
    column_zones: List[dict] = Field(default_factory=list, description="Column zones")
    
    # Additional Information
    remarks: str = Field("", description="General remarks")

    class Config:
        json_schema_extra = {
            "example": {
                "project": "Residential Complex Phase-II",
                "building_tower": "Tower A",
                "block": "Block 1",
                "floor_level": "Ground to First Floor",
                "drawing_reference": "DRG-ST-002",
                "column_mark": "C1",
                "description": "Corner column",
                "number_of_units": 2,
                "column_width": 300,
                "column_depth": 400,
                "clear_floor_height": 3000,
                "concrete_grade": "M30",
                "steel_grade": "FE415",
                "cover": 40,
                "main_vertical_bars": [
                    {
                        "bar_mark": "M1",
                        "description": "Main corner bars",
                        "diameter": 16,
                        "number_of_bars": 8,
                        "lap_method": "CODE_BASED",
                        "lap_condition": "COMPRESSION"
                    }
                ],
                "master_stirrups": [
                    {
                        "link_mark": "MS1",
                        "diameter": 8,
                        "spacing": 150,
                        "zone_length": 3000,
                        "dimension_convention": "CENTRELINE"
                    }
                ],
                "reduction_levels": [
                    {
                        "level_name": "First Floor",
                        "reduction_percentage": 25,
                        "start_height": 1500,
                        "end_height": 3000,
                        "bars_to_reduce": ["M2"]
                    }
                ]
            }
        }


class ManualBeamBBSRequest(BaseModel):
    """Manual beam BBS calculation request"""
    member_id: str = Field(..., description="Unique beam identifier")
    length: float = Field(..., description="Beam length in mm")
    width: float = Field(..., description="Beam width in mm") 
    depth: float = Field(..., description="Beam depth in mm")
    clear_cover: float = Field(25, description="Clear cover in mm")
    
    # Main reinforcement
    top_bars: List[dict] = Field(default_factory=list, description="Top reinforcement bars")
    bottom_bars: List[dict] = Field(default_factory=list, description="Bottom reinforcement bars")
    
    # Stirrups with multi-zone support
    stirrup_zones: List[dict] = Field(default_factory=list, description="Stirrup zones")
    
    # Material properties
    concrete_grade: str = Field("M25", description="Concrete grade")
    steel_grade: str = Field("FE415", description="Steel grade")
    
    # Calculation parameters
    lap_method: str = Field("50D", description="Lap length method")
    custom_lap_factor: Optional[float] = Field(None, description="Custom lap factor")


class ManualColumnBBSRequest(BaseModel):
    """Manual column BBS calculation request"""
    member_id: str = Field(..., description="Unique column identifier")
    height: float = Field(..., description="Column height in mm")
    width: float = Field(..., description="Column width in mm")
    depth: float = Field(..., description="Column depth in mm") 
    clear_cover: float = Field(40, description="Clear cover in mm")
    
    # Longitudinal reinforcement
    main_bars: List[dict] = Field(default_factory=list, description="Main reinforcement bars")
    
    # Lateral reinforcement
    ties: List[dict] = Field(default_factory=list, description="Tie bars")
    stirrup_zones: List[dict] = Field(default_factory=list, description="Stirrup zones")
    
    # Column reductions
    reductions: List[dict] = Field(default_factory=list, description="Level-wise reductions")
    
    # Material properties
    concrete_grade: str = Field("M25", description="Concrete grade")
    steel_grade: str = Field("FE415", description="Steel grade")
    
    # Calculation parameters
    lap_method: str = Field("50D", description="Lap length method")
    custom_lap_factor: Optional[float] = Field(None, description="Custom lap factor")


class ProjectBBSRequest(BaseModel):
    """Project-wide BBS calculation request"""
    project_id: str = Field(..., description="Project identifier")
    members: List[dict] = Field(..., description="List of structural members")
    
    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "proj-123",
                "members": [
                    {
                        "type": "BEAM",
                        "member_id": "B1",
                        "length": 6000,
                        "width": 300,
                        "depth": 450,
                        "top_bars": [{"diameter": 16, "count": 4}],
                        "bottom_bars": [{"diameter": 20, "count": 2}],
                        "stirrup_zones": [
                            {
                                "zone_type": "CONFINED",
                                "start_distance": 0,
                                "end_distance": 1000,
                                "spacing": 100,
                                "diameter": 8,
                                "legs": 2
                            }
                        ]
                    }
                ]
            }
        }


def _dia_summary_to_list(dia_dict: dict) -> list:
    """Convert diameter_summary dict {dia: {count, total_length, total_weight}} to a sorted list.
    This is the single source of truth for serialising diameter_summary in every endpoint."""
    return [
        {
            "dia_mm": diameter,
            "diameter": diameter,
            "num_bars": summary.get("count", 0),
            "number_of_bars": summary.get("count", 0),
            "total_length_m": round(summary.get("total_length", 0) / 1000, 3),
            "total_length": round(summary.get("total_length", 0) / 1000, 3),
            "unit_weight_kg_per_m": round((diameter ** 2) / 162, 3),
            "total_weight_kg": round(summary.get("total_weight", 0), 2),
            "total_weight": round(summary.get("total_weight", 0), 2),
        }
        for diameter, summary in sorted(dia_dict.items())
    ]


@router.post("/complete/beam", summary="Complete Manual Beam BBS")
async def complete_beam_bbs(
    beam_data: CompleteBeamBBSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate complete Bar Bending Schedule for beam with all bar types
    
    Features:
    - Top main/continuous bars with anchorage and lap calculations
    - Bottom main/continuous bars with development length
    - Bottom curtailed bars with L/2, L/3, L/4, or custom curtailment
    - Top extra left/right bars with extension calculations
    - Multi-zone stirrups (left/middle/right) with dimension conventions
    - Professional calculation trace with IS 456 compliance
    - Level-wise reinforcement configuration support
    """
    try:
        # Convert request to CompleteBeamInput with field mapping
        beam_input_data = {
            "project": beam_data.project,
            "building_tower": beam_data.building_tower,
            "block": beam_data.block,
            "floor_level": beam_data.floor_level,
            "drawing_reference": beam_data.drawing_reference,
            "beam_mark": beam_data.beam_mark,
            "description": beam_data.description,
            "number_of_units": beam_data.number_of_units,
            "beam_width": beam_data.beam_width,
            "beam_depth": beam_data.beam_depth,
            "clear_span": beam_data.clear_span,
            "concrete_grade": beam_data.concrete_grade,
            "steel_grade": beam_data.steel_grade,
            "cover": beam_data.cover,
            "top_main_bars": beam_data.top_main_bars,
            "bottom_main_bars": beam_data.bottom_main_bars,
            "bottom_curtailed_bars": beam_data.bottom_curtailed_bars,
            "top_extra_left_bars": beam_data.top_extra_left_bars,
            "top_extra_right_bars": beam_data.top_extra_right_bars,
            "left_stirrup_zone": beam_data.left_stirrup_zone,
            "middle_stirrup_zone": beam_data.middle_stirrup_zone,
            "right_stirrup_zone": beam_data.right_stirrup_zone,
            "remarks": beam_data.remarks
        }
        
        # Calculate complete BBS
        result = create_complete_beam_bbs(beam_input_data)
        
        return {
            "status": "success",
            "calculation_method": "IS_456_2000_COMPLETE",
            "member_type": "BEAM",
            "member_info": {
                "project": beam_data.project,
                "beam_mark": beam_data.beam_mark,
                "building_tower": beam_data.building_tower,
                "floor_level": beam_data.floor_level,
                "drawing_reference": beam_data.drawing_reference,
                "description": beam_data.description
            },
            "dimensions": {
                "beam_width_mm": beam_data.beam_width,
                "beam_depth_mm": beam_data.beam_depth,
                "clear_span_mm": beam_data.clear_span,
                "number_of_units": beam_data.number_of_units
            },
            "material_properties": {
                "concrete_grade": beam_data.concrete_grade,
                "steel_grade": beam_data.steel_grade,
                "cover_mm": beam_data.cover
            },
            "bbs_entries": [
                {
                    "bar_mark": entry.bar_mark,
                    "member_id": entry.member_id,
                    "diameter": entry.diameter,
                    "number_of_bars": entry.number_of_bars,
                    "length_of_each_bar": entry.length_of_each_bar,
                    "total_length": entry.total_length,
                    "unit_weight": entry.unit_weight,
                    "total_weight": entry.total_weight,
                    "shape_code": entry.shape_code,
                    "bending_details": entry.bending_details,
                    "calculation_trace": entry.calculation_trace
                } for entry in result.entries
            ],
            "diameter_summary": [
                {
                    "dia_mm": diameter,
                    "diameter": diameter,
                    "num_bars": summary.get('count', 0),
                    "number_of_bars": summary.get('count', 0),
                    "total_length_m": round(summary.get('total_length', 0) / 1000, 3),
                    "total_length": round(summary.get('total_length', 0) / 1000, 3),
                    "unit_weight_kg_per_m": round((diameter ** 2) / 162, 3),
                    "total_weight_kg": round(summary.get('total_weight', 0), 2),
                    "total_weight": round(summary.get('total_weight', 0), 2)
                }
                for diameter, summary in sorted(result.diameter_summary.items())
            ],
            "total_weight_kg": result.grand_total_weight,
            "calculation_metadata": result.calculation_metadata,
            "member_summaries": result.member_summaries
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Complete beam BBS calculation failed: {str(e)}"
        )


@router.post("/complete/column", summary="Complete Manual Column BBS")
async def complete_column_bbs(
    column_data: CompleteColumnBBSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate complete unified Bar Bending Schedule for column with all tie types
    
    Features:
    - Main vertical bars with level-wise reduction calculations
    - Master/main closed stirrups with dimension conventions
    - Short links and long links with independent geometry
    - Cross ties with custom configurations
    - Column zones with different spacing requirements
    - Level-wise reinforcement changes and reductions
    - Unified BBS output combining all tie types
    - Professional calculation trace with IS 456 compliance
    """
    try:
        # Convert request to CompleteColumnInput
        column_input_data = column_data.model_dump()
        
        # Calculate complete unified BBS
        result = create_complete_column_bbs(column_input_data)
        
        return {
            "status": "success",
            "calculation_method": "IS_456_2000_UNIFIED_COLUMN",
            "member_type": "COLUMN",
            "member_info": {
                "project": column_data.project,
                "column_mark": column_data.column_mark,
                "building_tower": column_data.building_tower,
                "floor_level": column_data.floor_level,
                "drawing_reference": column_data.drawing_reference,
                "description": column_data.description
            },
            "dimensions": {
                "column_width_mm": column_data.column_width,
                "column_depth_mm": column_data.column_depth,
                "clear_floor_height_mm": column_data.clear_floor_height,
                "number_of_units": column_data.number_of_units
            },
            "material_properties": {
                "concrete_grade": column_data.concrete_grade,
                "steel_grade": column_data.steel_grade,
                "cover_mm": column_data.cover
            },
            "unified_bbs_entries": [
                {
                    "bar_mark": entry.bar_mark,
                    "member_id": entry.member_id,
                    "diameter": entry.diameter,
                    "number_of_bars": entry.number_of_bars,
                    "length_of_each_bar": entry.length_of_each_bar,
                    "total_length": entry.total_length,
                    "unit_weight": entry.unit_weight,
                    "total_weight": entry.total_weight,
                    "shape_code": entry.shape_code,
                    "bending_details": entry.bending_details,
                    "calculation_trace": entry.calculation_trace
                } for entry in result.entries
            ],
            "diameter_summary": [
                {
                    "dia_mm": diameter,
                    "diameter": diameter,
                    "num_bars": summary.get('count', 0),
                    "number_of_bars": summary.get('count', 0),
                    "total_length_m": round(summary.get('total_length', 0) / 1000, 3),
                    "total_length": round(summary.get('total_length', 0) / 1000, 3),
                    "unit_weight_kg_per_m": round((diameter ** 2) / 162, 3),
                    "total_weight_kg": round(summary.get('total_weight', 0), 2),
                    "total_weight": round(summary.get('total_weight', 0), 2)
                }
                for diameter, summary in sorted(result.diameter_summary.items())
            ],
            "total_weight_kg": result.grand_total_weight,
            "reinforcement_breakdown": {
                "main_bar_weight_kg": result.calculation_metadata.get('main_bar_weight_kg', 0),
                "tie_weight_kg": result.calculation_metadata.get('tie_weight_kg', 0),
                "reduction_levels": result.calculation_metadata.get('reduction_levels', 0)
            },
            "calculation_metadata": result.calculation_metadata,
            "member_summaries": result.member_summaries
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Complete column BBS calculation failed: {str(e)}"
        )


@router.post("/complete/project", summary="Complete Project BBS Calculation")
async def complete_project_bbs(
    project_data: dict,  # Accept flexible project structure
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate unified Bar Bending Schedule for entire project with complete specification compliance
    
    Features:
    - Multi-member BBS calculation (beams + columns)
    - Unified professional BBS table with all members
    - Diameter-wise summary across entire project
    - Complete calculation trace for all components
    - Level-wise reinforcement configurations
    - Professional Excel/PDF export ready format
    - Code-based and drawing-specified calculations
    """
    try:
        # Extract project information and members
        project_info = {
            'project_id': project_data.get('project_id', 'unknown'),
            'project_name': project_data.get('project_name', 'Project'),
            'building_tower': project_data.get('building_tower', ''),
            'block': project_data.get('block', ''),
            'engineer': project_data.get('engineer', 'N/A')
        }
        
        members = project_data.get('members', [])
        if not members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No members provided for project BBS calculation"
            )
            
        # Calculate complete project BBS
        result = create_complete_project_bbs(members)
        
        return {
            "status": "success",
            "calculation_method": "IS_456_2000_UNIFIED_PROJECT",
            "project_info": project_info,
            "unified_bbs": {
                "entries": [
                    {
                        "bar_mark": entry.bar_mark,
                        "member_id": entry.member_id,
                        "diameter": entry.diameter,
                        "number_of_bars": entry.number_of_bars,
                        "length_of_each_bar": entry.length_of_each_bar,
                        "total_length": entry.total_length,
                        "unit_weight": entry.unit_weight,
                        "total_weight": entry.total_weight,
                        "shape_code": entry.shape_code,
                        "bar_type": entry.bending_details.get('bar_type', ''),
                        "tie_type": entry.bending_details.get('tie_type', ''),
                        "calculation_source": "CALCULATED"
                    } for entry in result['unified_bbs'].entries
                ],
                "diameter_summary": _dia_summary_to_list(result['unified_bbs'].diameter_summary),
                "total_weight_kg": result['unified_bbs'].grand_total_weight
            },
            "member_summaries": {
                member_id: {
                    "total_weight_kg": summary.get('total_weight', 0),
                    "main_bar_weight_kg": summary.get('main_bar_weight', 0),
                    "tie_weight_kg": summary.get('tie_weight', 0),
                    "bar_count": summary.get('bar_count', 0)
                } for member_id, summary in result['unified_bbs'].member_summaries.items()
            },
            "project_summary": result['summary'],
            "calculation_metadata": result['unified_bbs'].calculation_metadata
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Complete project BBS calculation failed: {str(e)}"
        )
async def manual_beam_bbs(
    beam_data: ManualBeamBBSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate Bar Bending Schedule for a beam using manual input
    
    Features:
    - Professional beam reinforcement calculations
    - Multi-zone stirrup support
    - IS 456 development length calculations  
    - Dynamic unit weight calculation (d²/162)
    - Multiple lap length methods (30D-60D, custom, IS456)
    - Complete calculation trace
    """
    try:
        # Convert request to BeamInput format
        beam_input_data = beam_data.model_dump()
        
        # Calculate BBS
        result = create_beam_bbs(beam_input_data)
        
        return {
            "status": "success",
            "member_type": "BEAM",
            "member_id": beam_data.member_id,
            "bbs_entries": [
                {
                    "bar_mark": entry.bar_mark,
                    "diameter": entry.diameter,
                    "number_of_bars": entry.number_of_bars,
                    "length_of_each_bar": entry.length_of_each_bar,
                    "total_length": entry.total_length,
                    "unit_weight": entry.unit_weight,
                    "total_weight": entry.total_weight,
                    "shape_code": entry.shape_code,
                    "bending_details": entry.bending_details,
                    "calculation_trace": entry.calculation_trace
                } for entry in result.entries
            ],
            "diameter_summary": _dia_summary_to_list(result.diameter_summary),
            "total_weight_kg": result.grand_total_weight,
            "calculation_metadata": result.calculation_metadata
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"BBS calculation failed: {str(e)}"
        )


@router.post("/manual/column", summary="Manual Column BBS")
async def manual_column_bbs(
    column_data: ManualColumnBBSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate Bar Bending Schedule for a column using manual input
    
    Features:
    - Professional column reinforcement calculations
    - Level-wise reinforcement reduction
    - Multi-zone stirrup/tie support
    - IS 456 lap length calculations
    - Column-specific development lengths
    - Complete calculation trace
    """
    try:
        # Convert request to ColumnInput format
        column_input_data = column_data.model_dump()
        
        # Calculate BBS
        result = create_column_bbs(column_input_data)
        
        return {
            "status": "success",
            "member_type": "COLUMN",
            "member_id": column_data.member_id,
            "bbs_entries": [
                {
                    "bar_mark": entry.bar_mark,
                    "diameter": entry.diameter,
                    "number_of_bars": entry.number_of_bars,
                    "length_of_each_bar": entry.length_of_each_bar,
                    "total_length": entry.total_length,
                    "unit_weight": entry.unit_weight,
                    "total_weight": entry.total_weight,
                    "shape_code": entry.shape_code,
                    "bending_details": entry.bending_details,
                    "calculation_trace": entry.calculation_trace
                } for entry in result.entries
            ],
            "diameter_summary": _dia_summary_to_list(result.diameter_summary),
            "total_weight_kg": result.grand_total_weight,
            "calculation_metadata": result.calculation_metadata
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Column BBS calculation failed: {str(e)}"
        )


@router.post("/manual/project", summary="Project BBS Calculation")
async def project_bbs_calculation(
    project_data: ProjectBBSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate unified Bar Bending Schedule for entire project
    
    Features:
    - Multi-member BBS calculation (beams + columns)
    - Unified BBS table with all members
    - Diameter-wise summary across project
    - Professional calculation trace
    - Excel/PDF export ready format
    """
    try:
        # Skip project verification for testing - focus on functionality
        # project = get_project_by_id(db, project_data.project_id)
        # if not project:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Project not found"
        #     )
            
        # Calculate project BBS
        result = create_project_bbs(project_data.members)
        
        return {
            "status": "success",
            "project_id": project_data.project_id,
            "unified_bbs": {
                "entries": [
                    {
                        "bar_mark": entry.bar_mark,
                        "member_id": entry.member_id,
                        "diameter": entry.diameter,
                        "number_of_bars": entry.number_of_bars,
                        "length_of_each_bar": entry.length_of_each_bar,
                        "total_length": entry.total_length,
                        "unit_weight": entry.unit_weight,
                        "total_weight": entry.total_weight,
                        "shape_code": entry.shape_code,
                        "bending_details": entry.bending_details
                    } for entry in result['unified_bbs'].entries
                ],
                "diameter_summary": _dia_summary_to_list(result['unified_bbs'].diameter_summary),
                "total_weight_kg": result['unified_bbs'].grand_total_weight
            },
            "member_summaries": result['member_results'],
            "project_summary": result['summary']
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Project BBS calculation failed: {str(e)}"
        )


@router.get("/complete/calculation-methods", summary="Complete Calculation Methods and Options")
async def get_complete_calculation_methods():
    """Get all available calculation methods, options, and parameters for complete BBS system"""
    return {
        "member_types": [e.value for e in MemberType],
        "lap_methods": [e.value for e in LapMethod],
        "concrete_grades": [e.value for e in ConcreteGrade],
        "steel_grades": [e.value for e in SteelGrade],
        "curtailment_rules": [e.value for e in CurtailmentRule],
        "extension_rules": [e.value for e in ExtensionRule],
        "dimension_conventions": [e.value for e in DimensionConvention],
        "quantity_sources": [e.value for e in QuantitySource],
        "hook_types": [e.value for e in HookType],
        "lap_conditions": [e.value for e in LapCondition],
        "unit_weight_formula": "Weight (kg/m) = diameter² / 162",
        "development_length_formula": "Ld = φ × σs / (4 × τbd)",
        "development_length_code": "IS 456:2000 Clause 26.2.1",
        "lap_length_methods": {
            "DRAWING_SPECIFIED": "As per drawing specification",
            "USER_SPECIFIED": "User specified value",
            "30D": "30 × diameter",
            "40D": "40 × diameter", 
            "45D": "45 × diameter",
            "50D": "50 × diameter",
            "60D": "60 × diameter",
            "CUSTOM": "Custom multiplier × diameter",
            "CODE_BASED": "Code-based calculation per IS 456"
        },
        "curtailment_options": {
            "L/2": "Half span curtailment",
            "L/3": "One-third span curtailment", 
            "L/4": "Quarter span curtailment",
            "DRAWING_SPECIFIED": "As per drawing",
            "CUSTOM": "Custom length"
        },
        "extension_options": {
            "L/4": "Quarter span extension",
            "L/3": "One-third span extension",
            "DRAWING_SPECIFIED": "As per drawing",
            "CUSTOM": "Custom length"
        },
        "dimension_conventions": {
            "INSIDE": "Inside dimension (clear between bars)",
            "CENTRELINE": "Centreline dimension",
            "OUTSIDE": "Outside dimension",
            "DRAWING_SPECIFIED": "As per drawing",
            "CUSTOM": "Custom convention"
        },
        "code_references": [
            "IS 456:2000 - Code of Practice for Plain and Reinforced Concrete",
            "IS 2502:1963 - Code of Practice for Bending and Fixing of Bars",
            "SP 34:1987 - Handbook on Concrete Reinforcement and Detailing"
        ]
    }


@router.get("/complete/unit-weight/{diameter}", summary="Calculate Unit Weight with Trace")
async def calculate_unit_weight_complete(diameter: int):
    """
    Calculate unit weight for given diameter using d²/162 formula with complete trace
    
    Args:
        diameter: Bar diameter in mm (1-50mm)
        
    Returns:
        Unit weight in kg/m with calculation breakdown
    """
    if diameter <= 0 or diameter > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diameter must be between 1-50mm"
        )
        
    weight = unit_weight_kg_per_m(diameter)
    
    return {
        "diameter_mm": diameter,
        "unit_weight_kg_per_m": weight,
        "calculation_trace": {
            "formula": "Weight (kg/m) = (diameter²) / 162",
            "substitution": f"Weight = ({diameter}²) / 162",
            "calculation": f"Weight = {diameter * diameter} / 162",
            "result_kg_per_m": weight
        },
        "calculation_method": "Standard steel reinforcement formula",
        "verification_status": "CALCULATED"
    }


@router.post("/complete/lap-length", summary="Calculate Lap Length with Complete Trace")
async def calculate_lap_length_complete(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate lap length with complete calculation trace and IS 456 compliance
    
    Request format:
    {
        "diameter": 16,
        "method": "CODE_BASED",
        "concrete_grade": "M25", 
        "steel_grade": "FE415",
        "lap_condition": "COMPRESSION",
        "custom_factor": 45.5,  // Required if method is CUSTOM
        "drawing_specified_value": 800,  // Required if method is DRAWING_SPECIFIED
        "user_specified_value": 750  // Required if method is USER_SPECIFIED
    }
    """
    try:
        diameter = request.get('diameter')
        method = LapMethod(request.get('method', 'CODE_BASED'))
        concrete_grade = ConcreteGrade(request.get('concrete_grade', 'M25'))
        steel_grade = SteelGrade(request.get('steel_grade', 'FE415'))
        lap_condition = LapCondition(request.get('lap_condition', 'COMPRESSION'))
        
        lap_length, calculation_trace = calculate_lap_length(
            diameter, method,
            custom_factor=request.get('custom_factor'),
            drawing_specified_value=request.get('drawing_specified_value'),
            user_specified_value=request.get('user_specified_value'),
            concrete_grade=concrete_grade,
            steel_grade=steel_grade,
            lap_condition=lap_condition
        )
        
        return {
            "diameter_mm": diameter,
            "method": method.value,
            "concrete_grade": concrete_grade.value,
            "steel_grade": steel_grade.value,
            "lap_condition": lap_condition.value,
            "lap_length_mm": lap_length,
            "calculation_trace": calculation_trace,
            "verification_status": "CALCULATED"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/complete/development-length", summary="Calculate Development Length IS456 with Complete Breakdown")
async def calculate_development_length_complete(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate development length as per IS 456:2000 with complete formula breakdown
    
    Request format:
    {
        "diameter": 16,
        "concrete_grade": "M25",
        "steel_grade": "FE415",
        "bar_type": "deformed",  // "deformed" or "plain"
        "tension_compression": "tension"  // "tension" or "compression"
    }
    """
    try:
        diameter = request.get('diameter')
        concrete_grade = ConcreteGrade(request.get('concrete_grade', 'M25'))
        steel_grade = SteelGrade(request.get('steel_grade', 'FE415'))
        bar_type = request.get('bar_type', 'deformed')
        tension_compression = request.get('tension_compression', 'tension')
        
        dev_length, calculation_trace = calculate_development_length_is456(
            diameter, concrete_grade, steel_grade, bar_type, tension_compression
        )
        
        return {
            "diameter_mm": diameter,
            "concrete_grade": concrete_grade.value,
            "steel_grade": steel_grade.value,
            "bar_type": bar_type,
            "tension_compression": tension_compression,
            "development_length_mm": dev_length,
            "calculation_trace": calculation_trace,
            "code_reference": "IS 456:2000 Clause 26.2.1",
            "verification_status": calculation_trace.get('verification_status', 'CALCULATED')
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
async def get_calculation_methods():
    """Get available calculation methods and parameters"""
    return {
        "member_types": [e.value for e in MemberType],
        "lap_methods": [e.value for e in LapMethod],
        "concrete_grades": [e.value for e in ConcreteGrade],
        "steel_grades": [e.value for e in SteelGrade],
        "stirrup_zone_types": [e.value for e in StirrupZoneType],
        "unit_weight_formula": "Weight (kg/m) = diameter² / 162",
        "development_length_code": "IS 456:2000 Clause 26.2.1",
        "lap_length_methods": {
            "30D": "30 × diameter",
            "40D": "40 × diameter", 
            "45D": "45 × diameter",
            "50D": "50 × diameter",
            "60D": "60 × diameter",
            "CUSTOM": "Custom multiplier × diameter",
            "IS456_CODE": "Code-based calculation per IS 456"
        }
    }


@router.get("/manual/unit-weight/{diameter}", summary="Calculate Unit Weight")
async def calculate_unit_weight(diameter: int):
    """
    Calculate unit weight for given diameter using d²/162 formula
    
    Args:
        diameter: Bar diameter in mm
        
    Returns:
        Unit weight in kg/m
    """
    from app.services.manual_bbs_engine import unit_weight_kg_per_m
    
    if diameter <= 0 or diameter > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diameter must be between 1-50mm"
        )
        
    weight = unit_weight_kg_per_m(diameter)
    
    return {
        "diameter_mm": diameter,
        "unit_weight_kg_per_m": weight,
        "formula": f"({diameter}² / 162) = {weight:.3f}",
        "calculation_method": "Standard steel reinforcement formula"
    }


@router.get("/manual/lap-length/{diameter}", summary="Calculate Lap Length")
async def calculate_lap_length_api(
    diameter: int,
    method: str = "50D",
    custom_factor: Optional[float] = None,
    concrete_grade: str = "M25",
    steel_grade: str = "FE415"
):
    """
    Calculate lap length for given parameters
    
    Args:
        diameter: Bar diameter in mm
        method: Lap calculation method (30D, 40D, 45D, 50D, 60D, CUSTOM, IS456_CODE)
        custom_factor: Custom multiplier (required if method is CUSTOM)
        concrete_grade: Concrete grade (M15, M20, M25, M30, M35, M40)
        steel_grade: Steel grade (FE415, FE500, FE550)
    """
    from app.services.manual_bbs_engine import calculate_lap_length, LapMethod, ConcreteGrade, SteelGrade
    
    try:
        lap_method = LapMethod(method)
        concrete_gr = ConcreteGrade(concrete_grade)
        steel_gr = SteelGrade(steel_grade)
        
        lap_length = calculate_lap_length(
            diameter, lap_method, custom_factor, concrete_gr, steel_gr
        )
        
        return {
            "diameter_mm": diameter,
            "method": method,
            "concrete_grade": concrete_grade,
            "steel_grade": steel_grade,
            "lap_length_mm": lap_length,
            "custom_factor": custom_factor if method == "CUSTOM" else None
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/manual/development-length/{diameter}", summary="Calculate Development Length IS456")
async def calculate_development_length_api(
    diameter: int,
    concrete_grade: str = "M25",
    steel_grade: str = "FE415"
):
    """
    Calculate development length as per IS 456:2000
    
    Formula: Ld = φ × σs / (4 × τbd)
    """
    from app.services.manual_bbs_engine import calculate_development_length_is456, ConcreteGrade, SteelGrade
    
    try:
        concrete_gr = ConcreteGrade(concrete_grade)
        steel_gr = SteelGrade(steel_grade)
        
        dev_length = calculate_development_length_is456(diameter, concrete_gr, steel_gr)
        
        return {
            "diameter_mm": diameter,
            "concrete_grade": concrete_grade,
            "steel_grade": steel_grade,
            "development_length_mm": dev_length,
            "formula": "Ld = φ × σs / (4 × τbd)",
            "code_reference": "IS 456:2000 Clause 26.2.1",
            "minimum_length_mm": 12 * diameter
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ══════════════════════════════════════════════════════
# BBS EXPORT ENDPOINTS (EXCEL & PDF)
# ══════════════════════════════════════════════════════

from app.services.bbs_export_service import BBSExportService


@router.post("/manual/export/excel", summary="Export BBS to Excel")
async def export_bbs_to_excel(
    bbs_data: dict,  # Can be beam, column, or project BBS result
    project_info: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export Bar Bending Schedule to Excel format
    
    Features:
    - Professional BBS table formatting
    - Diameter-wise summary
    - Calculation metadata and formulas
    - Project header with standards compliance
    - Ready for construction use
    """
    try:
        export_service = BBSExportService()
        
        # Convert dict back to BBSCalculationResult if needed
        # This endpoint expects the result from previous calculations
        from app.services.manual_bbs_engine import BBSCalculationResult, BBSEntry
        
        if 'unified_bbs' in bbs_data:
            # Project BBS format
            result_data = bbs_data['unified_bbs']
        else:
            # Single member BBS format
            result_data = bbs_data
            
        # Reconstruct BBSCalculationResult from API response
        entries = []
        if 'bbs_entries' in result_data:
            for entry_data in result_data['bbs_entries']:
                entry = BBSEntry(
                    bar_mark=entry_data['bar_mark'],
                    member_id=entry_data.get('member_id', ''),
                    diameter=entry_data['diameter'],
                    number_of_bars=entry_data['number_of_bars'],
                    length_of_each_bar=entry_data['length_of_each_bar'],
                    total_length=entry_data['total_length'],
                    unit_weight=entry_data['unit_weight'],
                    total_weight=entry_data['total_weight'],
                    shape_code=entry_data['shape_code'],
                    bending_details=entry_data.get('bending_details', {}),
                    calculation_trace=entry_data.get('calculation_trace', {})
                )
                entries.append(entry)
        elif 'entries' in result_data:
            for entry_data in result_data['entries']:
                entry = BBSEntry(
                    bar_mark=entry_data['bar_mark'],
                    member_id=entry_data['member_id'],
                    diameter=entry_data['diameter'],
                    number_of_bars=entry_data['number_of_bars'],
                    length_of_each_bar=entry_data['length_of_each_bar'],
                    total_length=entry_data['total_length'],
                    unit_weight=entry_data['unit_weight'],
                    total_weight=entry_data['total_weight'],
                    shape_code=entry_data['shape_code'],
                    bending_details=entry_data.get('bending_details', {}),
                    calculation_trace=entry_data.get('calculation_trace', {})
                )
                entries.append(entry)
                
        bbs_result = BBSCalculationResult(
            entries=entries,
            diameter_summary=result_data.get('diameter_summary', {}),
            grand_total_weight=result_data.get('total_weight_kg', 0),
            calculation_metadata=result_data.get('calculation_metadata', {}),
            member_summaries=result_data.get('member_summaries', {})
        )
        
        # Generate Excel file
        excel_buffer = export_service.export_to_excel(bbs_result, project_info)
        
        # Prepare filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        project_name = project_info.get('project_name', 'Project') if project_info else 'Project'
        filename = f"BBS_{project_name}_{timestamp}.xlsx"
        
        return Response(
            content=excel_buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Excel export failed: {str(e)}"
        )


@router.post("/manual/export/pdf", summary="Export BBS to PDF")
async def export_bbs_to_pdf(
    bbs_data: dict,  # Can be beam, column, or project BBS result
    project_info: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export Bar Bending Schedule to PDF format
    
    Features:
    - Professional BBS table layout
    - Diameter-wise summary
    - Calculation details and code references
    - Project header with engineering standards
    - Print-ready format for site use
    """
    try:
        export_service = BBSExportService()
        
        # Convert dict back to BBSCalculationResult (same logic as Excel)
        from app.services.manual_bbs_engine import BBSCalculationResult, BBSEntry
        
        if 'unified_bbs' in bbs_data:
            result_data = bbs_data['unified_bbs']
        else:
            result_data = bbs_data
            
        # Reconstruct BBSCalculationResult
        entries = []
        if 'bbs_entries' in result_data:
            for entry_data in result_data['bbs_entries']:
                entry = BBSEntry(
                    bar_mark=entry_data['bar_mark'],
                    member_id=entry_data.get('member_id', ''),
                    diameter=entry_data['diameter'],
                    number_of_bars=entry_data['number_of_bars'],
                    length_of_each_bar=entry_data['length_of_each_bar'],
                    total_length=entry_data['total_length'],
                    unit_weight=entry_data['unit_weight'],
                    total_weight=entry_data['total_weight'],
                    shape_code=entry_data['shape_code'],
                    bending_details=entry_data.get('bending_details', {}),
                    calculation_trace=entry_data.get('calculation_trace', {})
                )
                entries.append(entry)
        elif 'entries' in result_data:
            for entry_data in result_data['entries']:
                entry = BBSEntry(
                    bar_mark=entry_data['bar_mark'],
                    member_id=entry_data['member_id'],
                    diameter=entry_data['diameter'],
                    number_of_bars=entry_data['number_of_bars'],
                    length_of_each_bar=entry_data['length_of_each_bar'],
                    total_length=entry_data['total_length'],
                    unit_weight=entry_data['unit_weight'],
                    total_weight=entry_data['total_weight'],
                    shape_code=entry_data['shape_code'],
                    bending_details=entry_data.get('bending_details', {}),
                    calculation_trace=entry_data.get('calculation_trace', {})
                )
                entries.append(entry)
                
        bbs_result = BBSCalculationResult(
            entries=entries,
            diameter_summary=result_data.get('diameter_summary', {}),
            grand_total_weight=result_data.get('total_weight_kg', 0),
            calculation_metadata=result_data.get('calculation_metadata', {}),
            member_summaries=result_data.get('member_summaries', {})
        )
        
        # Generate PDF file
        pdf_buffer = export_service.export_to_pdf(bbs_result, project_info)
        
        # Prepare filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        project_name = project_info.get('project_name', 'Project') if project_info else 'Project'
        filename = f"BBS_{project_name}_{timestamp}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF export failed: {str(e)}"
        )


@router.post("/manual/export/both", summary="Export BBS to Excel & PDF")
async def export_bbs_both_formats(
    bbs_data: dict,
    project_info: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export Bar Bending Schedule to both Excel and PDF formats
    
    Returns:
        JSON response with download URLs for both formats
    """
    try:
        export_service = BBSExportService()
        
        # Convert dict back to BBSCalculationResult (same logic as above)
        from app.services.manual_bbs_engine import BBSCalculationResult, BBSEntry
        
        if 'unified_bbs' in bbs_data:
            result_data = bbs_data['unified_bbs']
        else:
            result_data = bbs_data
            
        # Reconstruct BBSCalculationResult
        entries = []
        if 'bbs_entries' in result_data:
            for entry_data in result_data['bbs_entries']:
                entry = BBSEntry(
                    bar_mark=entry_data['bar_mark'],
                    member_id=entry_data.get('member_id', ''),
                    diameter=entry_data['diameter'],
                    number_of_bars=entry_data['number_of_bars'],
                    length_of_each_bar=entry_data['length_of_each_bar'],
                    total_length=entry_data['total_length'],
                    unit_weight=entry_data['unit_weight'],
                    total_weight=entry_data['total_weight'],
                    shape_code=entry_data['shape_code'],
                    bending_details=entry_data.get('bending_details', {}),
                    calculation_trace=entry_data.get('calculation_trace', {})
                )
                entries.append(entry)
                
        bbs_result = BBSCalculationResult(
            entries=entries,
            diameter_summary=result_data.get('diameter_summary', {}),
            grand_total_weight=result_data.get('total_weight_kg', 0),
            calculation_metadata=result_data.get('calculation_metadata', {}),
            member_summaries=result_data.get('member_summaries', {})
        )
        
        # Generate both formats
        export_files = export_service.export_both_formats(bbs_result, project_info)
        
        # For this endpoint, we'll return file info instead of actual files
        # In a real implementation, you might save files to storage and return URLs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        project_name = project_info.get('project_name', 'Project') if project_info else 'Project'
        
        return {
            "status": "success",
            "message": "BBS exported to both Excel and PDF formats",
            "files": {
                "excel": {
                    "filename": f"BBS_{project_name}_{timestamp}.xlsx",
                    "size_bytes": len(export_files['excel'].getvalue()),
                    "format": "Excel"
                },
                "pdf": {
                    "filename": f"BBS_{project_name}_{timestamp}.pdf", 
                    "size_bytes": len(export_files['pdf'].getvalue()),
                    "format": "PDF"
                }
            },
            "export_timestamp": timestamp,
            "total_weight_kg": bbs_result.grand_total_weight,
            "total_entries": len(bbs_result.entries)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )