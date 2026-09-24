"""
Project Files API
=================
Upload, index and query structural drawings / schedules for BBS extraction.

Supports ANY file format. Automatic extraction for DXF and text-layer PDFs.
Cross-file querying finds member data across ALL uploaded files.
"""
from __future__ import annotations
import json
import os
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.project_file import ProjectFile
from app.crud import project as project_crud
from app.services.bbs_extractor import extract_file
from app.services.bbs_query import query_to_review, _index_all_marks

router = APIRouter()

MAX_BYTES = 50 * 1024 * 1024   # 50 MB


# ── Schemas ───────────────────────────────────────────

class ProjectFileOut(BaseModel):
    id:               str
    project_id:       str
    original_name:    str
    file_type:        str
    file_category:    Optional[str] = None
    file_size_kb:     Optional[float] = None
    extraction_status: str
    member_count:     Optional[int] = 0
    member_list:      Optional[str] = None
    extraction_notes: Optional[str] = None
    created_at:       datetime
    model_config = {"from_attributes": True}


class MemberIndexOut(BaseModel):
    beams:   List[str]
    columns: List[str]
    files:   List[ProjectFileOut]


# ── Helpers ───────────────────────────────────────────

def _check_project(db: Session, project_id: uuid.UUID, user: User):
    from app.models.user import UserRole
    p = project_crud.get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        if str(p.created_by) != str(user.id):
            raise HTTPException(403, "Access denied")
    return p


def _detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    return {"dxf": "dxf", ".dxf": "dxf", ".dwg": "dwg",
            ".pdf": "pdf", ".jpg": "image", ".jpeg": "image",
            ".png": "image", ".bmp": "image"}.get(ext, "other")


def _save_file(content: bytes, project_id: str, filename: str) -> str:
    """Save file to UPLOAD_DIR/bbs_files/. Returns path."""
    save_dir = os.path.join(settings.UPLOAD_DIR, "bbs_files", project_id)
    os.makedirs(save_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{os.path.basename(filename)}"
    path = os.path.join(save_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return path


# ── Upload file ───────────────────────────────────────

@router.post("/project/{project_id}/upload", response_model=ProjectFileOut, status_code=201,
             summary="Upload a drawing or schedule file for BBS extraction")
async def upload_file(
    project_id: uuid.UUID,
    file:        UploadFile = File(...),
    file_category: str = Form("auto"),   # auto | beam_schedule | column_schedule | etc.
    db:          Session = Depends(get_db),
    current_user: User   = Depends(get_current_active_user),
):
    """
    Upload any structural file (DXF, DWG, PDF, schedule, plan).
    Automatically extracts beam/column data for cross-file BBS queries.

    Supported:
    - DXF  → geometry + text extraction
    - PDF  → text-layer schedule extraction
    - Other → stored for manual reference
    """
    _check_project(db, project_id, current_user)

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds 50 MB limit")

    fname     = file.filename or "upload"
    ftype     = _detect_file_type(fname)
    file_path = None

    # Save to disk
    try:
        file_path = _save_file(content, str(project_id), fname)
    except Exception:
        pass   # non-fatal — extraction still works from bytes

    # Run extraction
    extracted = extract_file(content, fname, ftype)
    if file_category != "auto":
        extracted["category"] = file_category

    member_marks = extracted.get("member_list", [])

    pf = ProjectFile(
        project_id        = str(project_id),
        filename          = os.path.basename(file_path) if file_path else fname,
        original_name     = fname,
        file_type         = ftype,
        file_category     = extracted.get("category", "other"),
        file_path         = file_path,
        file_size_kb      = round(len(content) / 1024, 1),
        extraction_status = extracted.get("extraction_status", "pending"),
        extracted_data    = json.dumps(extracted),
        member_count      = len(member_marks),
        member_list       = ",".join(member_marks),
        extraction_notes  = "\n".join(extracted.get("warnings", [])),
        uploaded_by       = str(current_user.id),
    )
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return pf


# ── List files ────────────────────────────────────────

@router.get("/project/{project_id}", response_model=MemberIndexOut,
            summary="List all files + member index for a project")
def list_files(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    files = db.query(ProjectFile).filter(
        ProjectFile.project_id == str(project_id)
    ).order_by(ProjectFile.created_at).all()

    file_dicts = [
        {"extracted_data": f.extracted_data, "original_name": f.original_name,
         "filename": f.filename}
        for f in files
    ]
    index = _index_all_marks(file_dicts)

    return MemberIndexOut(
        beams   = index["beams"],
        columns = index["columns"],
        files   = files,
    )


# ── Get one file ──────────────────────────────────────

@router.get("/{file_id}", response_model=ProjectFileOut)
def get_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    pf = db.query(ProjectFile).filter(ProjectFile.id == str(file_id)).first()
    if not pf:
        raise HTTPException(404, "File not found")
    _check_project(db, uuid.UUID(pf.project_id), current_user)
    return pf


# ── Get extracted data for one file ──────────────────

@router.get("/{file_id}/extracted")
def get_extracted(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    pf = db.query(ProjectFile).filter(ProjectFile.id == str(file_id)).first()
    if not pf:
        raise HTTPException(404, "File not found")
    _check_project(db, uuid.UUID(pf.project_id), current_user)
    try:
        data = json.loads(pf.extracted_data or "{}")
    except Exception:
        data = {}
    return {
        "file_id":  str(file_id),
        "filename": pf.original_name,
        "category": pf.file_category,
        "status":   pf.extraction_status,
        "members":  pf.member_list,
        "beams":    data.get("beams", {}),
        "columns":  data.get("columns", {}),
        "geometry": data.get("geometry", {}),
        "global_params": data.get("global_params", {}),
        "warnings": data.get("warnings", []),
    }


# ── Delete file ───────────────────────────────────────

@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    pf = db.query(ProjectFile).filter(ProjectFile.id == str(file_id)).first()
    if not pf:
        raise HTTPException(404, "File not found")
    _check_project(db, uuid.UUID(pf.project_id), current_user)
    if pf.file_path and os.path.exists(pf.file_path):
        try:
            os.remove(pf.file_path)
        except Exception:
            pass
    db.delete(pf)
    db.commit()


# ── Cross-file member query ───────────────────────────

@router.get("/project/{project_id}/query/{member_query}",
            summary="Search ALL uploaded files for a member's BBS data")
def query_member(
    project_id:   uuid.UUID,
    member_query: str,
    member_type:  str = "beam",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Searches across ALL uploaded files for the requested member.

    Examples:
      /query/EB5        → find all data for beam EB5
      /query/all        → index all known members
      /query/C1         → find column C1 data
      /query/EB5,EB6    → find multiple beams

    Returns extracted data with source attribution and conflict detection.
    Engineer can review and correct before BBS calculation.
    """
    _check_project(db, project_id, current_user)

    files = db.query(ProjectFile).filter(
        ProjectFile.project_id == str(project_id),
        ProjectFile.extraction_status.in_(["complete", "partial"])
    ).all()

    if not files:
        return {
            "query":   member_query,
            "results": [],
            "count":   0,
            "message": "No processed files found. Upload drawing/schedule files first.",
            "all_available_members": {"beams": [], "columns": []},
        }

    file_dicts = [
        {"extracted_data": f.extracted_data, "original_name": f.original_name,
         "filename": f.filename}
        for f in files
    ]

    result = query_to_review(member_query, file_dicts, member_type)
    result["file_count"] = len(files)
    result["files_searched"] = [f.original_name for f in files]
    return result


# ── Cross-file BBS generation ─────────────────────────

@router.post("/project/{project_id}/generate-bbs",
             summary="Generate BBS sheet from cross-file extracted data")
def generate_bbs_from_files(
    project_id:   uuid.UUID,
    member_query: str = Form(...),
    member_type:  str = Form("beam"),
    sheet_title:  str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    1. Query all files for member data
    2. Build BBS inputs
    3. Run BBS engine
    4. Create BBSSheet + BBSBar records
    5. Return sheet ID + review
    """
    from app.services.bbs_query import query_member as qm
    from app.services.bbs_engine import (
        BeamBarInput, ColumnBarInput, StirrupInput,
        calc_beam_main_bar, calc_column_main_bar, calc_stirrups,
        MISSING,
    )
    from app.models.bbs import BBSSheet, BBSBar

    _check_project(db, project_id, current_user)

    files = db.query(ProjectFile).filter(
        ProjectFile.project_id == str(project_id),
        ProjectFile.extraction_status.in_(["complete", "partial"])
    ).all()

    if not files:
        raise HTTPException(400, "No processed files. Upload files first.")

    file_dicts = [
        {"extracted_data": f.extracted_data, "original_name": f.original_name}
        for f in files
    ]

    datasets = qm(member_query, file_dicts, member_type)

    # Count existing sheets for auto-numbering
    existing = db.query(BBSSheet).filter(BBSSheet.project_id == str(project_id)).count()
    sheet_num = f"BBS-{existing + 1:03d}"
    title = sheet_title or f"Auto BBS — {member_query.upper()}"

    # Global params
    gp_fck, gp_fy, gp_cover = 20, 500, 25
    for ds in datasets:
        fv = ds.get("fck");   gp_fck   = fv["value"] or gp_fck   if fv["status"]=="found" else gp_fck
        fv = ds.get("fy");    gp_fy    = fv["value"] or gp_fy    if fv["status"]=="found" else gp_fy
        fv = ds.get("cover_mm"); gp_cover = fv["value"] or gp_cover if fv["status"]=="found" else gp_cover

    sheet = BBSSheet(
        project_id   = str(project_id),
        sheet_number = sheet_num,
        title        = title,
        member_type  = member_type,
        mode         = "auto",
        fck          = int(gp_fck), fy = int(gp_fy),
        clear_cover  = float(gp_cover),
        prepared_by  = str(current_user.id),
    )
    db.add(sheet)
    db.flush()

    bars_created = []
    flags_all    = []
    sort_idx     = 0

    for ds in datasets:
        inp = ds.to_bbs_inputs()
        flags_all.extend(inp.get("_flags", []))

        # Heading row for this member
        heading = BBSBar(
            sheet_id   = sheet.id,
            sort_order = sort_idx,
            is_heading = True,
            bar_mark   = ds.mark,
            position   = f"{ds.member_type.upper()} — {ds.mark}",
            source     = "auto",
            status     = "calculated",
        )
        db.add(heading)
        sort_idx += 1

        def _src(field_name):
            r = ds.get(field_name)
            return r.get("source", "auto") if r.get("status") == "found" else "auto"

        # Build bar rows based on member type
        if member_type == "column":
            # Main bars
            mb_dia  = inp.get("dia_mm")    or inp.get("top_dia_mm")
            mb_num  = inp.get("num_bars")  or inp.get("top_num_bars")
            sh      = inp.get("storey_height_mm")

            if mb_dia and sh:
                ci = ColumnBarInput(
                    storey_height_mm = float(sh),
                    dia_mm           = int(mb_dia),
                    num_bars         = int(mb_num or 4),
                    cover_mm         = float(inp.get("cover_mm") or gp_cover),
                    fck=int(gp_fck), fy=int(gp_fy),
                )
                res = calc_column_main_bar(ci, ds.mark)
                main_bar = BBSBar(
                    sheet_id=sheet.id, sort_order=sort_idx,
                    bar_mark=f"{ds.mark}-M", position="Main Bars",
                    member_mark=ds.mark,
                    dia_mm=res.dia_mm, num_bars=res.num_bars,
                    bar_shape="straight", storey_height_mm=sh,
                    cover_mm=float(inp.get("cover_mm") or gp_cover),
                    lap_mm=res.lap_length_mm,
                    cutting_length_mm=res.cutting_length_mm,
                    total_length_mm=res.total_length_mm,
                    unit_weight_kg_per_m=res.unit_weight_kg_per_m,
                    total_weight_kg=res.total_weight_kg,
                    formula=res.formula, source=_src("dia_mm"), status=res.status,
                )
                db.add(main_bar)
                bars_created.append(main_bar)
                sort_idx += 1
            else:
                _add_missing(db, sheet.id, ds.mark, sort_idx, member_type,
                             inp, gp_cover, flags_all)
                sort_idx += 2

        else:
            # Beam — bottom bars, top bars, stirrups
            span    = inp.get("clear_span_mm")
            b_dia   = inp.get("bottom_dia_mm")
            b_num   = inp.get("bottom_num_bars")
            t_dia   = inp.get("top_dia_mm")
            t_num   = inp.get("top_num_bars")
            st_dia  = inp.get("stirrup_dia_mm")
            st_spc  = inp.get("stirrup_spacing_mm")
            sec_b   = inp.get("section_b_mm") or (inp.get("size", {}) or {}).get("b")
            sec_d   = inp.get("section_d_mm") or (inp.get("size", {}) or {}).get("d")
            cover   = float(inp.get("cover_mm") or gp_cover)

            if span and b_dia:
                bi = BeamBarInput(
                    clear_span_mm=float(span),
                    dia_mm=int(b_dia), num_bars=int(b_num or 2),
                    has_hook_near=True, has_hook_far=True,
                    fck=int(gp_fck), fy=int(gp_fy),
                )
                res = calc_beam_main_bar(bi, f"{ds.mark}-B")
                bot_bar = BBSBar(
                    sheet_id=sheet.id, sort_order=sort_idx,
                    bar_mark=f"{ds.mark}-B", position="Bottom Steel",
                    member_mark=ds.mark, section_b_mm=sec_b, section_d_mm=sec_d,
                    dia_mm=res.dia_mm, num_bars=res.num_bars,
                    bar_shape="straight", clear_span_mm=float(span),
                    cover_mm=cover, has_hook_near=True, has_hook_far=True,
                    cutting_length_mm=res.cutting_length_mm,
                    total_length_mm=res.total_length_mm,
                    unit_weight_kg_per_m=res.unit_weight_kg_per_m,
                    total_weight_kg=res.total_weight_kg,
                    formula=res.formula, source=_src("bottom_dia_mm"), status=res.status,
                )
                db.add(bot_bar)
                bars_created.append(bot_bar)
                sort_idx += 1

            if span and t_dia:
                ti = BeamBarInput(
                    clear_span_mm=float(span),
                    dia_mm=int(t_dia), num_bars=int(t_num or 2),
                    has_hook_near=True, has_hook_far=True,
                    fck=int(gp_fck), fy=int(gp_fy),
                )
                res = calc_beam_main_bar(ti, f"{ds.mark}-T")
                top_bar = BBSBar(
                    sheet_id=sheet.id, sort_order=sort_idx,
                    bar_mark=f"{ds.mark}-T", position="Top Steel",
                    member_mark=ds.mark, section_b_mm=sec_b, section_d_mm=sec_d,
                    dia_mm=res.dia_mm, num_bars=res.num_bars,
                    bar_shape="straight", clear_span_mm=float(span),
                    cover_mm=cover, has_hook_near=True, has_hook_far=True,
                    cutting_length_mm=res.cutting_length_mm,
                    total_length_mm=res.total_length_mm,
                    unit_weight_kg_per_m=res.unit_weight_kg_per_m,
                    total_weight_kg=res.total_weight_kg,
                    formula=res.formula, source=_src("top_dia_mm"), status=res.status,
                )
                db.add(top_bar)
                bars_created.append(top_bar)
                sort_idx += 1

            if st_dia and sec_b and sec_d:
                si = StirrupInput(
                    b_mm=float(sec_b), d_mm=float(sec_d),
                    dia_mm=int(st_dia),
                    cover_mm=cover,
                    spacing_mm=float(st_spc or 150),
                    zone_length_mm=float(span or 0),
                )
                res = calc_stirrups(si, f"{ds.mark}-ST")
                st_bar = BBSBar(
                    sheet_id=sheet.id, sort_order=sort_idx,
                    bar_mark=f"{ds.mark}-ST", position="Stirrups",
                    member_mark=ds.mark, section_b_mm=sec_b, section_d_mm=sec_d,
                    dia_mm=res.dia_mm, num_bars=res.num_stirrups,
                    bar_shape="stirrup_rect",
                    spacing_mm=float(st_spc or 150), cover_mm=cover,
                    cutting_length_mm=res.cutting_length_mm,
                    total_length_mm=res.total_length_mm,
                    unit_weight_kg_per_m=res.unit_weight_kg_per_m,
                    total_weight_kg=res.total_weight_kg,
                    formula=res.formula, source=_src("stirrup_dia_mm"), status=res.status,
                )
                db.add(st_bar)
                bars_created.append(st_bar)
                sort_idx += 1

            if not (span and (b_dia or t_dia)):
                _add_missing(db, sheet.id, ds.mark, sort_idx, member_type,
                             inp, gp_cover, flags_all)
                sort_idx += 2

    db.commit()
    db.refresh(sheet)

    total_wt = sum(b.total_weight_kg or 0 for b in bars_created)

    return {
        "sheet_id":       sheet.id,
        "sheet_number":   sheet.sheet_number,
        "title":          sheet.title,
        "bars_created":   len(bars_created),
        "total_weight_kg": round(total_wt, 3),
        "flags":          flags_all,
        "message": (
            "BBS sheet created. Review bars in the BBS tab. "
            + (f"{len(flags_all)} field(s) need verification." if flags_all else "All fields extracted.")
        ),
    }


def _add_missing(db, sheet_id, mark, sort_idx, mtype, inp, cover, flags):
    """Add a 'missing input' bar row so engineer knows what to fill."""
    from app.models.bbs import BBSBar
    from app.services.bbs_query import NOT_FOUND

    missing_fields = [f["field"] for f in inp.get("_flags", [])]
    bar = BBSBar(
        sheet_id   = sheet_id,
        sort_order = sort_idx,
        bar_mark   = f"{mark}-?",
        position   = "Incomplete — missing: " + ", ".join(missing_fields[:4]),
        member_mark = mark,
        bar_shape  = "straight",
        source     = "auto",
        status     = "missing_input",
        remarks    = NOT_FOUND + " — " + ", ".join(missing_fields),
    )
    db.add(bar)
