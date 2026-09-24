"""
Project Files API — Complete professional BBS
=============================================
Handles: multi-file upload, extraction, cross-file query,
natural-language BBS calculation, complete project BBS generation.
"""
from __future__ import annotations
import json, os, uuid, math
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
from app.models.bbs import BBSSheet, BBSBar
from app.crud import project as project_crud
from app.services.bbs_extractor import extract_file
from app.services.bbs_query import query_member as qm_engine, _index_all_marks
from app.services.bbs_nlp import parse_request, describe_request, get_required_params
from app.services.bbs_engine import (
    BeamBarInput, ColumnBarInput, StirrupInput, StirrupZone,
    SlabBarInput, FootingBarInput,
    calc_beam_bar, calc_column_bar, calc_stirrups,
    calc_slab_bar, calc_footing_bar,
    diameter_summary, development_length, lap_length, unit_weight_kg_per_m,
)

router = APIRouter()
MAX_BYTES = 50 * 1024 * 1024


# ── Schemas ───────────────────────────────────────────

class ProjectFileOut(BaseModel):
    id: str; project_id: str
    original_name: str; file_type: str
    file_category: Optional[str] = None
    file_size_kb:  Optional[float] = None
    extraction_status: str
    extraction_method: Optional[str] = None
    member_count:  Optional[int] = 0
    member_list:   Optional[str] = None
    extraction_notes: Optional[str] = None
    capability_notes: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class MemberIndexOut(BaseModel):
    beams: List[str]; columns: List[str]
    files: List[ProjectFileOut]


# ── Auth helper ───────────────────────────────────────

def _check_project(db, project_id, user):
    from app.models.user import UserRole
    p = project_crud.get_project_by_id(db, project_id)
    if not p: raise HTTPException(404, "Project not found")
    if user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        if str(p.created_by) != str(user.id):
            raise HTTPException(403, "Access denied")
    return p


def _file_type(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    return {".dxf":"dxf",".dwg":"dwg",".pdf":"pdf",
            ".png":"image",".jpg":"image",".jpeg":"image",".bmp":"image",
            ".xlsx":"xlsx",".xls":"xlsx",".csv":"csv"}.get(ext,"other")


def _save(content: bytes, project_id: str, filename: str) -> str:
    d = os.path.join(settings.UPLOAD_DIR, "bbs_files", project_id)
    os.makedirs(d, exist_ok=True)
    safe = f"{uuid.uuid4().hex[:8]}_{os.path.basename(filename)}"
    p = os.path.join(d, safe)
    with open(p, "wb") as f: f.write(content)
    return p


# ═══════════════════════════════════════════════════════
# UPLOAD
# ═══════════════════════════════════════════════════════

@router.post("/project/{project_id}/upload", response_model=ProjectFileOut, status_code=201)
async def upload_file(
    project_id:    uuid.UUID,
    file:          UploadFile = File(...),
    file_category: str = Form("auto"),
    db:     Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload any structural file. Automatic extraction is attempted for all formats."""
    _check_project(db, project_id, current_user)
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File exceeds 50 MB")

    fname  = file.filename or "upload"
    ftype  = _file_type(fname)
    fpath  = None
    try: fpath = _save(content, str(project_id), fname)
    except Exception: pass

    extracted = extract_file(content, fname, ftype)
    if file_category != "auto":
        extracted["category"] = file_category

    marks = extracted.get("member_list", [])
    cap   = "; ".join(extracted.get("capability_notes", []))

    pf = ProjectFile(
        project_id=str(project_id),
        filename=os.path.basename(fpath) if fpath else fname,
        original_name=fname, file_type=ftype,
        file_category=extracted.get("category","other"),
        file_path=fpath, file_size_kb=round(len(content)/1024, 1),
        extraction_status=extracted.get("extraction_status","pending"),
        extracted_data=json.dumps(extracted),
        member_count=len(marks), member_list=",".join(marks),
        extraction_notes="\n".join(extracted.get("warnings",[])),
        capability_notes=cap,
        uploaded_by=str(current_user.id),
    )
    db.add(pf); db.commit(); db.refresh(pf)
    return pf


# ── List files ────────────────────────────────────────

@router.get("/project/{project_id}", response_model=MemberIndexOut)
def list_files(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    files = db.query(ProjectFile).filter(
        ProjectFile.project_id == str(project_id)
    ).order_by(ProjectFile.created_at).all()
    fd = [{"extracted_data":f.extracted_data,"original_name":f.original_name} for f in files]
    idx = _index_all_marks(fd)
    return MemberIndexOut(beams=idx["beams"], columns=idx["columns"], files=files)


@router.get("/{file_id}", response_model=ProjectFileOut)
def get_file(file_id: uuid.UUID, db=Depends(get_db), current_user=Depends(get_current_active_user)):
    pf = db.query(ProjectFile).filter(ProjectFile.id==str(file_id)).first()
    if not pf: raise HTTPException(404)
    _check_project(db, uuid.UUID(pf.project_id), current_user)
    return pf


@router.get("/{file_id}/extracted")
def get_extracted(file_id: uuid.UUID, db=Depends(get_db), current_user=Depends(get_current_active_user)):
    pf = db.query(ProjectFile).filter(ProjectFile.id==str(file_id)).first()
    if not pf: raise HTTPException(404)
    _check_project(db, uuid.UUID(pf.project_id), current_user)
    data = json.loads(pf.extracted_data or "{}")
    return {
        "file_id": str(file_id), "filename": pf.original_name,
        "category": pf.file_category, "status": pf.extraction_status,
        "extraction_method": data.get("extraction_method",""),
        "capability_notes": data.get("capability_notes",[]),
        "members": pf.member_list, "beams": data.get("beams",{}),
        "columns": data.get("columns",{}), "geometry": data.get("geometry",{}),
        "global_params": data.get("global_params",{}), "warnings": data.get("warnings",[]),
    }


@router.delete("/{file_id}", status_code=204)
def delete_file(file_id: uuid.UUID, db=Depends(get_db), current_user=Depends(get_current_active_user)):
    pf = db.query(ProjectFile).filter(ProjectFile.id==str(file_id)).first()
    if not pf: raise HTTPException(404)
    _check_project(db, uuid.UUID(pf.project_id), current_user)
    if pf.file_path and os.path.exists(pf.file_path):
        try: os.remove(pf.file_path)
        except: pass
    db.delete(pf); db.commit()


# ═══════════════════════════════════════════════════════
# CROSS-FILE QUERY
# ═══════════════════════════════════════════════════════

@router.get("/project/{project_id}/query/{member_query}")
def query_member(
    project_id: uuid.UUID, member_query: str,
    member_type: str = "beam",
    db=Depends(get_db), current_user=Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    files = db.query(ProjectFile).filter(
        ProjectFile.project_id==str(project_id),
        ProjectFile.extraction_status.in_(["complete","partial"])
    ).all()
    if not files:
        return {"query":member_query,"results":[],"count":0,
                "message":"No processed files. Upload files first.",
                "all_available_members":{"beams":[],"columns":[]}}
    fd = [{"extracted_data":f.extracted_data,"original_name":f.original_name} for f in files]
    from app.services.bbs_query import query_to_review
    result = query_to_review(member_query, fd, member_type)
    result["file_count"]      = len(files)
    result["files_searched"]  = [f.original_name for f in files]
    return result


# ═══════════════════════════════════════════════════════
# NATURAL-LANGUAGE BBS REQUEST
# ═══════════════════════════════════════════════════════

@router.post("/project/{project_id}/nl-request")
async def nl_bbs_request(
    project_id: uuid.UUID,
    user_input: str = Form(...),
    db=Depends(get_db), current_user=Depends(get_current_active_user),
):
    """
    Natural-language BBS calculation request.
    Parses the request, searches all project files, builds calculation dataset,
    runs BBS engine, returns results + creates BBS sheet.
    """
    _check_project(db, project_id, current_user)

    req     = parse_request(user_input)
    desc    = describe_request(req)
    req_params = get_required_params(req)

    # Load all project files
    files = db.query(ProjectFile).filter(
        ProjectFile.project_id==str(project_id),
        ProjectFile.extraction_status.in_(["complete","partial"])
    ).all()

    fd = [{"extracted_data":f.extracted_data,"original_name":f.original_name} for f in files]

    # Determine which members to process
    if req.scope == "project" or req.members == ["all"]:
        idx   = _index_all_marks(fd)
        marks = idx.get("beams",[]) if req.member_type in ("beam","all") else []
        marks += idx.get("columns",[]) if req.member_type in ("column","all") else []
    else:
        marks = req.members

    if not marks:
        return {
            "parsed_request": desc,
            "required_params": req_params,
            "members_found": [],
            "result": None,
            "message": "No matching members found in project files.",
            "sheet_id": None,
        }

    # Generate BBS sheet
    gen_result = _generate_bbs_sheet(
        db=db, project_id=str(project_id), marks=marks,
        member_type=req.member_type, file_dicts=fd,
        title=f"Auto BBS — {user_input[:60]}",
        current_user_id=str(current_user.id),
    )

    return {
        "parsed_request": desc,
        "required_params": req_params,
        "members_processed": marks,
        "files_searched": [f.original_name for f in files],
        **gen_result,
    }


# ═══════════════════════════════════════════════════════
# COMPLETE PROJECT BBS (member-type-scoped)
# ═══════════════════════════════════════════════════════

@router.post("/project/{project_id}/generate-complete-bbs")
async def generate_complete_bbs(
    project_id:  uuid.UUID,
    member_type: str = Form("all"),   # all|beam|column|slab|footing
    sheet_title: str = Form(""),
    db=Depends(get_db), current_user=Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    files = db.query(ProjectFile).filter(
        ProjectFile.project_id==str(project_id),
        ProjectFile.extraction_status.in_(["complete","partial"])
    ).all()
    if not files:
        raise HTTPException(400, "No processed files. Upload files first.")

    fd  = [{"extracted_data":f.extracted_data,"original_name":f.original_name} for f in files]
    idx = _index_all_marks(fd)

    marks = []
    if member_type in ("all","beam"):    marks += idx.get("beams",[])
    if member_type in ("all","column"):  marks += idx.get("columns",[])

    title = sheet_title or f"Complete BBS — {member_type.upper()}"
    gen   = _generate_bbs_sheet(
        db=db, project_id=str(project_id), marks=marks,
        member_type=member_type, file_dicts=fd, title=title,
        current_user_id=str(current_user.id),
    )
    gen["members_processed"] = marks
    gen["files_searched"]    = [f.original_name for f in files]
    return gen


@router.post("/project/{project_id}/generate-bbs")
async def generate_bbs_from_files(
    project_id:   uuid.UUID,
    member_query: str = Form(...),
    member_type:  str = Form("beam"),
    sheet_title:  str = Form(""),
    db=Depends(get_db), current_user=Depends(get_current_active_user),
):
    _check_project(db, project_id, current_user)
    files = db.query(ProjectFile).filter(
        ProjectFile.project_id==str(project_id),
        ProjectFile.extraction_status.in_(["complete","partial"])
    ).all()
    if not files:
        raise HTTPException(400, "No processed files.")

    fd    = [{"extracted_data":f.extracted_data,"original_name":f.original_name} for f in files]
    idx   = _index_all_marks(fd)

    if member_query.strip().lower() == "all":
        marks = idx.get("beams",[]) + idx.get("columns",[])
    else:
        marks = [m.strip().upper() for m in re.split(r'[,\s]+', member_query) if m.strip()]

    title = sheet_title or f"BBS — {member_query.upper()}"
    gen   = _generate_bbs_sheet(
        db=db, project_id=str(project_id), marks=marks,
        member_type=member_type, file_dicts=fd, title=title,
        current_user_id=str(current_user.id),
    )
    gen["members_processed"] = marks
    gen["files_searched"]    = [f.original_name for f in files]
    return gen


# ═══════════════════════════════════════════════════════
# CORE BBS GENERATION
# ═══════════════════════════════════════════════════════

import re as _re

def _get(dataset: dict, key: str, default=None):
    """Safe get from bbs_inputs dict."""
    v = dataset.get(key)
    if v is None: return default
    if isinstance(v, dict) and "b" in v and "d" in v:
        return v
    return v


def _generate_bbs_sheet(
    db, project_id: str, marks: list, member_type: str,
    file_dicts: list, title: str, current_user_id: str,
) -> dict:
    from app.services.bbs_query import query_member as qm

    existing  = db.query(BBSSheet).filter(BBSSheet.project_id==project_id).count()
    sheet_num = f"BBS-{existing+1:03d}"

    # Extract global params
    gp_fck, gp_fy, gp_cover = 20, 500, 25
    for fd in file_dicts:
        try:
            d = json.loads(fd.get("extracted_data") or "{}")
            gp = d.get("global_params", {})
            if gp.get("fck"):   gp_fck   = gp["fck"]
            if gp.get("fy"):    gp_fy    = gp["fy"]
            if gp.get("cover"): gp_cover = gp["cover"]
        except Exception: pass

    sheet = BBSSheet(
        project_id=project_id, sheet_number=sheet_num, title=title,
        member_type=member_type, mode="auto",
        fck=int(gp_fck), fy=int(gp_fy), clear_cover=float(gp_cover),
        prepared_by=current_user_id,
    )
    db.add(sheet); db.flush()

    bars_created = 0
    flags_all    = []
    sort_idx     = 0
    extraction_review = []

    for mark in marks:
        # Determine member type for this mark
        mtype = member_type
        if mtype == "all":
            mtype = "column" if _re.match(r'E?C\d', mark, re.I) else "beam"

        # Query cross-file
        datasets = qm(mark, file_dicts, mtype)
        if not datasets: continue
        ds  = datasets[0]
        inp = ds.to_bbs_inputs()

        # Extraction review entry
        rev_entry = {
            "mark": mark, "type": mtype,
            "fields": {k: ds.get(k) for k in ds._fields},
            "flags": inp.get("_flags", []),
        }
        extraction_review.append(rev_entry)
        flags_all.extend(inp.get("_flags", []))

        # ── Heading row ───────────────────────────────
        heading = BBSBar(
            sheet_id=sheet.id, sort_order=sort_idx, is_heading=True,
            bar_mark=mark, position=f"{mtype.upper()} — {mark}", source="auto",
        )
        db.add(heading); sort_idx += 1

        cover = float(_get(inp,"cover_mm") or gp_cover)
        fck   = int(_get(inp,"fck") or gp_fck)
        fy    = int(_get(inp,"fy")  or gp_fy)

        if mtype == "column":
            _add_column_bars(db, sheet, inp, sort_idx, cover, fck, fy, mark)
            sort_idx += 4
        else:
            _add_beam_bars(db, sheet, inp, sort_idx, cover, fck, fy, mark)
            sort_idx += 5

        bars_created += 1

    db.commit(); db.refresh(sheet)

    bars = [b for b in sheet.bars if not b.is_heading and b.dia_mm]
    total_wt = round(sum(b.total_weight_kg or 0 for b in bars), 3)
    dia_sum  = diameter_summary([
        {"dia_mm":b.dia_mm,"total_length_mm":b.total_length_mm or 0,
         "total_weight_kg":b.total_weight_kg or 0,"num_bars":b.num_bars or 0}
        for b in bars
    ])

    return {
        "sheet_id": sheet.id, "sheet_number": sheet_num, "title": title,
        "members_count": len(marks), "bars_created": bars_created,
        "total_weight_kg": total_wt,
        "diameter_summary": list(dia_sum.values()),
        "extraction_review": extraction_review,
        "flags": flags_all,
        "message": (
            f"BBS sheet {sheet_num} created. "
            + (f"{len(flags_all)} field(s) need verification. " if flags_all else "")
            + "Review in BBS tab → Manual BBS."
        ),
    }


def _add_beam_bars(db, sheet, inp, sort_idx, cover, fck, fy, mark):
    span = _get(inp, "clear_span_mm")
    b_d  = _get(inp, "bottom_dia_mm")
    b_n  = _get(inp, "bottom_num_bars")
    t_d  = _get(inp, "top_dia_mm")
    t_n  = _get(inp, "top_num_bars")
    st_d = _get(inp, "stirrup_dia_mm")
    st_s = _get(inp, "stirrup_spacing_mm")
    sz   = _get(inp, "size") or {}
    sec_b = _get(inp,"section_b_mm") or (sz.get("b") if isinstance(sz,dict) else None)
    sec_d = _get(inp,"section_d_mm") or (sz.get("d") if isinstance(sz,dict) else None)
    src   = "auto"

    if span and b_d:
        bi   = BeamBarInput(clear_span_mm=float(span),dia_mm=int(b_d),num_bars=int(b_n or 2),
                             position="bottom",has_hook_near=True,has_hook_far=True,fck=fck,fy=fy,source=src)
        res  = calc_beam_bar(bi, f"{mark}-B")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-B",
                      position="Bottom Steel",member_mark=mark,section_b_mm=sec_b,section_d_mm=sec_d,
                      dia_mm=res.dia_mm,num_bars=res.num_bars,bar_shape="straight",
                      clear_span_mm=float(span),cover_mm=cover,has_hook_near=True,has_hook_far=True,
                      cutting_length_mm=res.cutting_length_mm,total_length_mm=res.total_length_mm,
                      unit_weight_kg_per_m=res.unit_weight,total_weight_kg=res.total_weight_kg,
                      formula=res.formula,source=src,status=res.status)); sort_idx+=1

    if span and t_d:
        ti   = BeamBarInput(clear_span_mm=float(span),dia_mm=int(t_d),num_bars=int(t_n or 2),
                             position="top",has_hook_near=True,has_hook_far=True,fck=fck,fy=fy,source=src)
        res  = calc_beam_bar(ti, f"{mark}-T")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-T",
                      position="Top Steel",member_mark=mark,section_b_mm=sec_b,section_d_mm=sec_d,
                      dia_mm=res.dia_mm,num_bars=res.num_bars,bar_shape="straight",
                      clear_span_mm=float(span),cover_mm=cover,has_hook_near=True,has_hook_far=True,
                      cutting_length_mm=res.cutting_length_mm,total_length_mm=res.total_length_mm,
                      unit_weight_kg_per_m=res.unit_weight,total_weight_kg=res.total_weight_kg,
                      formula=res.formula,source=src,status=res.status)); sort_idx+=1

    if st_d and sec_b and sec_d:
        zones = [StirrupZone("Full Span", float(span or 0), float(st_s or 150))]
        si  = StirrupInput(b_mm=float(sec_b),d_mm=float(sec_d),dia_mm=int(st_d),
                            cover_mm=cover,zones=zones,source=src)
        res = calc_stirrups(si, f"{mark}-ST")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-ST",
                      position="Stirrups",member_mark=mark,section_b_mm=sec_b,section_d_mm=sec_d,
                      dia_mm=res.dia_mm,num_bars=res.total_num,bar_shape="stirrup_rect",
                      spacing_mm=float(st_s or 150),cover_mm=cover,clear_span_mm=float(span or 0),
                      cutting_length_mm=res.cutting_length_mm,total_length_mm=res.total_length_mm,
                      unit_weight_kg_per_m=res.unit_weight,total_weight_kg=res.total_weight_kg,
                      formula=res.formula,source=src,status=res.status)); sort_idx+=1

    if not (span and (b_d or t_d)):
        missing = []
        if not span:  missing.append("clear_span_mm")
        if not b_d:   missing.append("bottom_dia_mm")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-?",
                      position=f"INCOMPLETE: {', '.join(missing)}",
                      member_mark=mark,source="auto",status="missing_input",
                      remarks="NOT_FOUND / VERIFICATION REQUIRED — " + ", ".join(missing)))


def _add_column_bars(db, sheet, inp, sort_idx, cover, fck, fy, mark):
    sh    = _get(inp,"storey_height_mm")
    m_d   = _get(inp,"main_dia_mm") or _get(inp,"dia_mm")
    m_n   = _get(inp,"num_main_bars") or _get(inp,"num_bars")
    tie_d = _get(inp,"tie_dia_mm")
    tie_s = _get(inp,"tie_spacing_mm")
    sz    = _get(inp,"size") or {}
    sec_b = _get(inp,"section_b_mm") or (sz.get("b") if isinstance(sz,dict) else None)
    sec_d = _get(inp,"section_d_mm") or (sz.get("d") if isinstance(sz,dict) else None)
    src   = "auto"

    if sh and m_d:
        ci   = ColumnBarInput(storey_height_mm=float(sh),dia_mm=int(m_d),
                               num_bars=int(m_n or 4),cover_mm=cover,fck=fck,fy=fy,source=src)
        res  = calc_column_bar(ci, f"{mark}-M")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-M",
                      position="Main Bars",member_mark=mark,section_b_mm=sec_b,section_d_mm=sec_d,
                      dia_mm=res.dia_mm,num_bars=res.num_bars,bar_shape="straight",
                      storey_height_mm=float(sh),cover_mm=cover,lap_mm=res.lap_length_mm,
                      cutting_length_mm=res.cutting_length_mm,total_length_mm=res.total_length_mm,
                      unit_weight_kg_per_m=res.unit_weight,total_weight_kg=res.total_weight_kg,
                      formula=res.formula,source=src,status=res.status)); sort_idx+=1

    if tie_d and sec_b and sec_d:
        zones = [StirrupZone("Full Height", float(sh or 0), float(tie_s or 150))]
        ti  = StirrupInput(b_mm=float(sec_b),d_mm=float(sec_d),dia_mm=int(tie_d),
                            cover_mm=cover,zones=zones,hook_type="135",source=src)
        res = calc_stirrups(ti, f"{mark}-TI")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-TI",
                      position="Ties",member_mark=mark,section_b_mm=sec_b,section_d_mm=sec_d,
                      dia_mm=res.dia_mm,num_bars=res.total_num,bar_shape="stirrup_rect",
                      spacing_mm=float(tie_s or 150),cover_mm=cover,storey_height_mm=float(sh or 0),
                      cutting_length_mm=res.cutting_length_mm,total_length_mm=res.total_length_mm,
                      unit_weight_kg_per_m=res.unit_weight,total_weight_kg=res.total_weight_kg,
                      formula=res.formula,source=src,status=res.status)); sort_idx+=1

    if not (sh and m_d):
        missing = []
        if not sh:  missing.append("storey_height_mm")
        if not m_d: missing.append("main_dia_mm")
        db.add(BBSBar(sheet_id=sheet.id,sort_order=sort_idx,bar_mark=f"{mark}-?",
                      position=f"INCOMPLETE: {', '.join(missing)}",
                      member_mark=mark,source="auto",status="missing_input",
                      remarks="NOT_FOUND / VERIFICATION REQUIRED — " + ", ".join(missing)))
