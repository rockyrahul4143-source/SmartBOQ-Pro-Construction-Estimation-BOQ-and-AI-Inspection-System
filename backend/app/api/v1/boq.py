from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.db.base import get_db
from app.core.dependencies import get_current_active_user, require_admin_or_pm
from app.crud import boq as boq_crud
from app.crud import project as project_crud
from app.models.user import User
from app.schemas.boq import (
    BOQCreate, BOQUpdate, BOQOut, BOQListItem,
    BOQItemCreate, BOQItemUpdate, BOQItemOut,
)
from app.schemas.auth import MessageResponse

router = APIRouter()


def _get_boq_or_404(db, boq_id):
    b = boq_crud.get_boq_by_id(db, boq_id)
    if not b:
        raise HTTPException(status_code=404, detail="BOQ not found")
    return b


# ── List BOQs for a project ───────────────────────────
@router.get("/project/{project_id}", response_model=List[BOQListItem],
            summary="List all BOQs for a project")
def list_boqs(
    project_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    p = project_crud.get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return boq_crud.get_boqs_by_project(db, project_id)


# ── Create BOQ ────────────────────────────────────────
@router.post("/", response_model=BOQOut, status_code=status.HTTP_201_CREATED,
             summary="Create a new BOQ (empty)")
def create_boq(
    payload: BOQCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    p = project_crud.get_project_by_id(db, payload.project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return boq_crud.create_boq(db, payload, current_user.id)


# ── Auto-generate BOQ from estimates ──────────────────
@router.post("/{boq_id}/auto-generate", response_model=BOQOut,
             summary="Auto-populate BOQ items from saved quantity estimates")
def auto_generate(
    boq_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    Reads all saved Estimate rows for the BOQ's project and creates
    a properly sectioned BOQ with correct quantities.
    Engineer still needs to fill in rates.
    """
    boq = _get_boq_or_404(db, boq_id)
    return boq_crud.auto_generate_from_estimates(db, boq)


# ── Get BOQ ───────────────────────────────────────────
@router.get("/{boq_id}", response_model=BOQOut, summary="Get full BOQ with all line items")
def get_boq(
    boq_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return _get_boq_or_404(db, boq_id)


# ── Update BOQ ────────────────────────────────────────
@router.put("/{boq_id}", response_model=BOQOut, summary="Update BOQ header (title, %, status)")
def update_boq(
    boq_id: UUID,
    payload: BOQUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    boq = _get_boq_or_404(db, boq_id)
    return boq_crud.update_boq(db, boq, payload)


# ── Approve BOQ ───────────────────────────────────────
@router.post("/{boq_id}/approve", response_model=BOQOut,
             summary="Mark BOQ as approved (Admin/PM only)")
def approve_boq(
    boq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_pm),
):
    boq = _get_boq_or_404(db, boq_id)
    return boq_crud.approve_boq(db, boq, current_user.id)


# ── Delete BOQ ────────────────────────────────────────
@router.delete("/{boq_id}", response_model=MessageResponse,
               summary="Delete a BOQ (Admin/PM only)")
def delete_boq(
    boq_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_pm),
):
    boq = _get_boq_or_404(db, boq_id)
    boq_crud.delete_boq(db, boq)
    return MessageResponse(message="BOQ deleted.")


# ── BOQ Items ─────────────────────────────────────────
@router.post("/{boq_id}/items", response_model=BOQItemOut,
             status_code=status.HTTP_201_CREATED, summary="Add a line item to BOQ")
def add_item(
    boq_id: UUID,
    payload: BOQItemCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_boq_or_404(db, boq_id)
    return boq_crud.add_item(db, boq_id, payload)


@router.put("/{boq_id}/items/{item_id}", response_model=BOQItemOut,
            summary="Update a BOQ line item")
def update_item(
    boq_id: UUID,
    item_id: UUID,
    payload: BOQItemUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    from app.models.boq import BOQItem
    item = db.query(BOQItem).filter(
        BOQItem.id == str(item_id),
        BOQItem.boq_id == str(boq_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return boq_crud.update_item(db, item, payload)


@router.delete("/{boq_id}/items/{item_id}", response_model=MessageResponse,
               summary="Delete a BOQ line item")
def delete_item(
    boq_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    from app.models.boq import BOQItem
    item = db.query(BOQItem).filter(
        BOQItem.id == str(item_id),
        BOQItem.boq_id == str(boq_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    boq_crud.delete_item(db, item)
    return MessageResponse(message="Item deleted.")
