from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from datetime import datetime

from app.models.project import Project, ProjectStatus, BuildingType
from app.schemas.project import ProjectCreate, ProjectUpdate


def _generate_project_code(db: Session) -> str:
    year  = datetime.utcnow().year
    count = db.query(func.count(Project.id)).scalar() + 1
    # Ensure uniqueness by checking collision
    code = f"SBP-{year}-{count:04d}"
    while db.query(Project).filter(Project.project_code == code).first():
        count += 1
        code = f"SBP-{year}-{count:04d}"
    return code


def get_project_by_id(db: Session, project_id: UUID) -> Optional[Project]:
    return db.query(Project).filter(Project.id == str(project_id)).first()


def get_project_by_code(db: Session, code: str) -> Optional[Project]:
    return db.query(Project).filter(Project.project_code == code).first()


def get_projects(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: Optional[ProjectStatus] = None,
    building_type: Optional[BuildingType] = None,
    search: Optional[str] = None,
    created_by: Optional[UUID] = None,
) -> Tuple[List[Project], int]:
    q = db.query(Project)
    if status:
        q = q.filter(Project.status == status)
    if building_type:
        q = q.filter(Project.building_type == building_type)
    if search:
        pat = f"%{search}%"
        q = q.filter(or_(
            Project.project_name.ilike(pat),
            Project.client_name.ilike(pat),
            Project.project_code.ilike(pat),
            Project.location.ilike(pat),
        ))
    if created_by:
        q = q.filter(Project.created_by == str(created_by))
    total    = q.count()
    projects = q.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    return projects, total


def create_project(db: Session, payload: ProjectCreate, user_id: UUID) -> Project:
    project = Project(
        **payload.model_dump(),
        project_code=_generate_project_code(db),
        created_by=str(user_id),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, payload: ProjectUpdate) -> Project:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    db.delete(project)
    db.commit()


def archive_project(db: Session, project: Project) -> Project:
    project.status = ProjectStatus.ARCHIVED
    db.commit()
    db.refresh(project)
    return project


def get_project_stats(db: Session, user_id: Optional[UUID] = None) -> dict:
    # ── FIXED: apply user filter to cost_sum too ──
    q = db.query(Project)
    if user_id:
        q = q.filter(Project.created_by == str(user_id))

    total    = q.count()
    # Re-apply user filter to cost aggregation
    cost_q   = db.query(func.coalesce(func.sum(Project.total_estimated_cost), 0))
    if user_id:
        cost_q = cost_q.filter(Project.created_by == str(user_id))
    cost_sum = float(cost_q.scalar() or 0)

    # ── FIXED: fresh query per status to avoid filter accumulation ──
    by_status = {}
    for s in ProjectStatus:
        status_q = db.query(Project)
        if user_id:
            status_q = status_q.filter(Project.created_by == str(user_id))
        by_status[s.value] = status_q.filter(Project.status == s).count()

    return {
        "total_projects":       total,
        **by_status,
        "total_estimated_cost": cost_sum,
    }


def get_recent_projects(db: Session, limit: int = 5, user_id: Optional[UUID] = None) -> List[Project]:
    q = db.query(Project).filter(Project.status != ProjectStatus.ARCHIVED)
    if user_id:
        q = q.filter(Project.created_by == str(user_id))
    return q.order_by(Project.updated_at.desc()).limit(limit).all()
