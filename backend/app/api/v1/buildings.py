from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.crud import building as building_crud
from app.crud import project as project_crud
from app.models.user import User
from app.schemas.building import (
    BuildingCreate, BuildingUpdate, BuildingOut, RoomCreate, RoomOut,
)
from app.schemas.auth import MessageResponse

router = APIRouter()


def _get_project_or_404(db, project_id):
    p = project_crud.get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return p


def _get_building_or_404(db, building_id):
    b = building_crud.get_building_by_id(db, building_id)
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    return b


# ── Building CRUD ─────────────────────────────────────
@router.get("/project/{project_id}", response_model=List[BuildingOut],
            summary="List buildings for a project")
def list_buildings(
    project_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_project_or_404(db, project_id)
    return building_crud.get_buildings_by_project(db, project_id)


@router.post("/", response_model=BuildingOut, status_code=status.HTTP_201_CREATED,
             summary="Add building information to a project")
def create_building(
    payload: BuildingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_project_or_404(db, payload.project_id)
    return building_crud.create_building(db, payload)


@router.get("/{building_id}", response_model=BuildingOut, summary="Get building details")
def get_building(
    building_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return _get_building_or_404(db, building_id)


@router.put("/{building_id}", response_model=BuildingOut, summary="Update building dimensions")
def update_building(
    building_id: UUID,
    payload: BuildingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    building = _get_building_or_404(db, building_id)
    return building_crud.update_building(db, building, payload)


@router.delete("/{building_id}", response_model=MessageResponse, summary="Delete a building")
def delete_building(
    building_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    building = _get_building_or_404(db, building_id)
    building_crud.delete_building(db, building)
    return MessageResponse(message="Building deleted.")


# ── Room CRUD ─────────────────────────────────────────
@router.get("/{building_id}/rooms", response_model=List[RoomOut],
            summary="List all rooms in a building")
def list_rooms(
    building_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_building_or_404(db, building_id)
    return building_crud.get_rooms_by_building(db, building_id)


@router.post("/{building_id}/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED,
             summary="Add a room to a building")
def add_room(
    building_id: UUID,
    payload: RoomCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    _get_building_or_404(db, building_id)
    return building_crud.create_room(db, building_id, payload)


@router.delete("/{building_id}/rooms/{room_id}", response_model=MessageResponse,
               summary="Delete a room")
def delete_room(
    building_id: UUID,
    room_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    deleted = building_crud.delete_room(db, room_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return MessageResponse(message="Room deleted.")
