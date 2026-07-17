from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.dependencies import get_current_active_user, require_admin_or_pm
from app.crud import project as project_crud
from app.models.user import User
from app.models.project import ProjectStatus, BuildingType
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut,
    ProjectListItem, ProjectStats,
)
from app.schemas.auth import MessageResponse

router = APIRouter()


# ── List Projects ─────────────────────────────────────
@router.get("/", summary="List all projects with filters and pagination")
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[ProjectStatus] = None,
    building_type: Optional[BuildingType] = None,
    search: Optional[str] = Query(None, min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns paginated project list.
    Admins see all projects; other roles see only projects they created.
    """
    from app.models.user import UserRole
    owned_only = current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER)

    projects, total = project_crud.get_projects(
        db,
        skip=skip,
        limit=limit,
        status=status,
        building_type=building_type,
        search=search,
        created_by=current_user.id if owned_only else None,
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [ProjectListItem.model_validate(p) for p in projects],
    }


# ── Stats ─────────────────────────────────────────────
@router.get("/stats", response_model=ProjectStats, summary="Dashboard project statistics")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.user import UserRole
    owned_only = current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER)
    return project_crud.get_project_stats(
        db, user_id=current_user.id if owned_only else None
    )


# ── Recent ────────────────────────────────────────────
@router.get("/recent", response_model=List[ProjectListItem], summary="5 most recently updated projects")
def get_recent(db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    return project_crud.get_recent_projects(db)


# ── Create ────────────────────────────────────────────
@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED,
             summary="Create a new project")
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return project_crud.create_project(db, payload, current_user.id)


# ── Get by ID ─────────────────────────────────────────
@router.get("/{project_id}", response_model=ProjectOut, summary="Get project details")
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    _check_access(project, current_user)
    return project


# ── Update ────────────────────────────────────────────
@router.put("/{project_id}", response_model=ProjectOut, summary="Update project details")
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    _check_access(project, current_user)
    return project_crud.update_project(db, project, payload)


# ── Archive ───────────────────────────────────────────
@router.post("/{project_id}/archive", response_model=ProjectOut, summary="Archive a project")
def archive_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    _check_access(project, current_user)
    return project_crud.archive_project(db, project)


# ── Delete ────────────────────────────────────────────
@router.delete("/{project_id}", response_model=MessageResponse, summary="Delete a project")
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_pm),
):
    project = project_crud.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    name = project.project_name
    project_crud.delete_project(db, project)
    return MessageResponse(message=f"Project '{name}' deleted.")


# ── Helper ────────────────────────────────────────────
def _check_access(project, user: User):
    from app.models.user import UserRole
    if user.role in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        return
    if str(project.created_by) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this project")
