from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
import io

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.crud import boq as boq_crud
from app.crud import project as project_crud
from app.crud.estimate import get_estimates_by_project
from app.models.user import User
from app.services.report_generator import (
    generate_boq_pdf, generate_boq_excel, generate_boq_csv,
    generate_quantity_pdf,
)

router = APIRouter()


def _project_or_404(db, project_id):
    p = project_crud.get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _boq_or_404(db, boq_id):
    b = boq_crud.get_boq_by_id(db, boq_id)
    if not b:
        raise HTTPException(status_code=404, detail="BOQ not found")
    return b


# ── BOQ Reports ───────────────────────────────────────
@router.get("/boq/{boq_id}/pdf", summary="Download BOQ as PDF")
def boq_pdf(
    boq_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    boq = _boq_or_404(db, boq_id)
    project = _project_or_404(db, boq.project_id)
    pdf_bytes = generate_boq_pdf(boq, project)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=BOQ_{boq.boq_number}.pdf"},
    )


@router.get("/boq/{boq_id}/excel", summary="Download BOQ as Excel")
def boq_excel(
    boq_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    boq = _boq_or_404(db, boq_id)
    project = _project_or_404(db, boq.project_id)
    excel_bytes = generate_boq_excel(boq, project)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=BOQ_{boq.boq_number}.xlsx"},
    )


@router.get("/boq/{boq_id}/csv", summary="Download BOQ as CSV")
def boq_csv(
    boq_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    boq = _boq_or_404(db, boq_id)
    project = _project_or_404(db, boq.project_id)
    csv_str = generate_boq_csv(boq, project)
    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=BOQ_{boq.boq_number}.csv"},
    )


# ── Quantity Reports ──────────────────────────────────
@router.get("/quantity/{project_id}/pdf", summary="Download Quantity Report as PDF")
def quantity_pdf(
    project_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    project = _project_or_404(db, project_id)
    estimates = get_estimates_by_project(db, project_id)
    if not estimates:
        raise HTTPException(status_code=404, detail="No estimates found. Run estimation first.")
    pdf_bytes = generate_quantity_pdf(estimates, project)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Qty_{project.project_code}.pdf"},
    )


@router.get("/quantity/{project_id}/csv", summary="Download Quantity Report as CSV")
def quantity_csv(
    project_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    project = _project_or_404(db, project_id)
    estimates = get_estimates_by_project(db, project_id)
    if not estimates:
        raise HTTPException(status_code=404, detail="No estimates found.")
    import csv, io
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Project", project.project_name])
    w.writerow(["Work Type", "Unit", "Quantity", "Cement Bags", "Sand CFT",
                "Aggregate CFT", "Steel KG", "Bricks", "Paint Ltr", "Tiles m2"])
    for e in estimates:
        w.writerow([
            e.work_type.value, e.unit, e.quantity,
            e.cement_bags or 0, e.sand_cft or 0, e.aggregate_cft or 0,
            e.steel_kg or 0, e.bricks_nos or 0, e.paint_ltr or 0, e.tiles_sqm or 0,
        ])
    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Qty_{project.project_code}.csv"},
    )
