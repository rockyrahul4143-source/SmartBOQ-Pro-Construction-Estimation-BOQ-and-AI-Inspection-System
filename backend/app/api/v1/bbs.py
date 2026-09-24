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
from pydantic import BaseModel, Field

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.bbs import BBSSheet, BBSBar
from app.crud import project as project_crud
from app.services.bbs_engine import (
    BeamBarInput, ColumnBarInput, StirrupInput,
    calc_beam_main_bar, calc_column_main_bar, calc_stirrups,
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
    extra_length_mm:   float = 0.0

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
    p = project_crud.get_project_by_id(db, project_id)
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
            bar.unit_weight_kg_per_m = res.unit_weight_kg_per_m
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
            res = calc_column_main_bar(inp, bar.bar_mark or "C")
            bar.cutting_length_mm    = res.cutting_length_mm
            bar.lap_mm               = res.lap_length_mm
            bar.total_length_mm      = res.total_length_mm
            bar.unit_weight_kg_per_m = res.unit_weight_kg_per_m
            bar.total_weight_kg      = res.total_weight_kg
            bar.formula = res.formula
            bar.status  = res.status

    else:
        if bar.clear_span_mm:
            inp = BeamBarInput(
                clear_span_mm=bar.clear_span_mm,
                support_width_near_mm=bar.support_near_mm or 230.0,
                support_width_far_mm=bar.support_far_mm or 230.0,
                dia_mm=bar.dia_mm, num_bars=bar.num_bars or 2,
                has_hook_near=bar.has_hook_near,
                has_hook_far=bar.has_hook_far,
                hook_type=bar.hook_type or "standard",
                splice_required=bool(bar.lap_mm and bar.lap_mm > 0),
                fck=fck, fy=fy, bond_type=bt, source=bar.source,
            )
            res = calc_beam_main_bar(inp, bar.bar_mark or "B")
            bar.cutting_length_mm    = res.cutting_length_mm
            bar.lap_mm               = res.lap_length_mm
            bar.total_length_mm      = res.total_length_mm
            bar.unit_weight_kg_per_m = res.unit_weight_kg_per_m
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
        support_width_near_mm=req.support_near_mm,
        support_width_far_mm=req.support_far_mm,
        dia_mm=req.dia_mm, num_bars=req.num_bars,
        has_hook_near=req.has_hook_near, has_hook_far=req.has_hook_far,
        hook_type=req.hook_type, splice_required=req.splice_required,
        fck=req.fck, fy=req.fy, bond_type=req.bond_type,
    )
    r = calc_beam_main_bar(inp)
    return r.__dict__


@router.post("/calc/column-bar")
def calc_col(req: ColumnBarCalcReq, _: User = Depends(get_current_active_user)):
    inp = ColumnBarInput(
        storey_height_mm=req.storey_height_mm,
        dia_mm=req.dia_mm, num_bars=req.num_bars,
        cover_mm=req.cover_mm, lap_mm=req.lap_mm,
        fck=req.fck, fy=req.fy, extra_length_mm=req.extra_length_mm,
    )
    r = calc_column_main_bar(inp)
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
