from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.db.base import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User, UserRole
from app.models.project import Project, ProjectStatus, BuildingType
from app.models.estimate import Estimate, WorkType
from app.models.boq import BOQ
from app.models.material import Material, MaterialRateHistory
from app.crud import project as project_crud

router = APIRouter()


def _base_query(db: Session, user: User):
    """Return a fresh base Project query scoped to the user's role."""
    if user.role in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        return db.query(Project)
    return db.query(Project).filter(Project.created_by == str(user.id))


@router.get("/dashboard", summary="Master dashboard KPIs and summary data")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    total_projects  = _base_query(db, current_user).count()
    active_projects = _base_query(db, current_user).filter(Project.status == ProjectStatus.ACTIVE).count()

    # Cost sum scoped to user
    cost_q = _base_query(db, current_user)
    cost_sum = float(
        db.query(func.coalesce(func.sum(Project.total_estimated_cost), 0))
        .filter(Project.id.in_([p.id for p in cost_q.with_entities(Project.id)]))
        .scalar() or 0
    )

    total_materials = db.query(Material).filter(Material.is_active == True).count()
    total_boqs      = db.query(BOQ).count()

    recent = _base_query(db, current_user).order_by(Project.updated_at.desc()).limit(5).all()

    # ── Status chart — FIXED: fresh query per status to avoid filter accumulation ──
    status_chart = []
    for s in ProjectStatus:
        count = _base_query(db, current_user).filter(Project.status == s).count()
        status_chart.append({"status": s.value, "count": count})

    # ── Building type chart ──
    type_chart = []
    for bt in BuildingType:
        count = _base_query(db, current_user).filter(Project.building_type == bt).count()
        if count > 0:
            type_chart.append({"type": bt.value, "count": count})

    return {
        "kpis": {
            "total_projects":       total_projects,
            "active_projects":      active_projects,
            "total_estimated_cost": cost_sum,
            "total_materials":      total_materials,
            "total_boqs":           total_boqs,
        },
        "recent_projects": [
            {
                "id":             str(p.id),
                "project_code":   p.project_code,
                "project_name":   p.project_name,
                "client_name":    p.client_name,
                "status":         p.status.value,
                "estimated_cost": p.total_estimated_cost or 0,
                "updated_at":     p.updated_at.isoformat(),
            }
            for p in recent
        ],
        "charts": {
            "status_distribution":        status_chart,
            "building_type_distribution": type_chart,
        },
    }


@router.get("/cost-trends", summary="Monthly project cost trends (last N months)")
def cost_trends(
    months: int = Query(12, ge=3, le=24),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    start_date = datetime.utcnow() - timedelta(days=months * 30)

    # ── FIXED: use strftime for SQLite compatibility instead of extract() ──
    # Detect dialect safely for SQLAlchemy 2.x
    try:
        dialect_name = db.get_bind().dialect.name
    except Exception:
        try:
            dialect_name = db.bind.dialect.name
        except Exception:
            dialect_name = "sqlite"   # safe default

    is_sqlite = "sqlite" in dialect_name

    if is_sqlite:
        rows = db.execute(text("""
            SELECT
                CAST(strftime('%Y', created_at) AS INTEGER) AS year,
                CAST(strftime('%m', created_at) AS INTEGER) AS month,
                COUNT(id) AS project_count,
                COALESCE(SUM(total_estimated_cost), 0) AS total_cost
            FROM projects
            WHERE created_at >= :start_date
            GROUP BY strftime('%Y', created_at), strftime('%m', created_at)
            ORDER BY year, month
        """), {"start_date": start_date.isoformat()}).fetchall()
    else:
        from sqlalchemy import extract
        rows = (
            db.query(
                extract("year",  Project.created_at).label("year"),
                extract("month", Project.created_at).label("month"),
                func.count(Project.id).label("project_count"),
                func.coalesce(func.sum(Project.total_estimated_cost), 0).label("total_cost"),
            )
            .filter(Project.created_at >= start_date)
            .group_by(
                extract("year",  Project.created_at),
                extract("month", Project.created_at),
            )
            .order_by(
                extract("year",  Project.created_at),
                extract("month", Project.created_at),
            )
            .all()
        )

    result = []
    for r in rows:
        try:
            y, m = int(r[0]), int(r[1])
            result.append({
                "year":          y,
                "month":         m,
                "month_label":   datetime(y, m, 1).strftime("%b %Y"),
                "project_count": int(r[2]),
                "total_cost":    float(r[3]),
            })
        except Exception:
            continue
    return result


@router.get("/material-usage", summary="Aggregate material consumption across all projects")
def material_usage(
    project_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = db.query(Estimate)
    if project_id:
        # Verify caller can access this specific project
        p = project_crud.get_project_by_id(db, project_id) if project_id else None
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        if current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
            if str(p.created_by) != str(current_user.id):
                raise HTTPException(status_code=403, detail="You do not have access to this project")
        q = q.filter(Estimate.project_id == str(project_id))
    elif current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        # Scope to only this user's projects
        owned_ids = [str(p.id) for p in db.query(Project).filter(
            Project.created_by == str(current_user.id)
        ).all()]
        q = q.filter(Estimate.project_id.in_(owned_ids))
    rows = q.all()

    totals = {
        "cement_bags":   round(sum(r.cement_bags   or 0 for r in rows), 1),
        "sand_cft":      round(sum(r.sand_cft      or 0 for r in rows), 1),
        "aggregate_cft": round(sum(r.aggregate_cft or 0 for r in rows), 1),
        "steel_kg":      round(sum(r.steel_kg      or 0 for r in rows), 1),
        "bricks_nos":    round(sum(r.bricks_nos    or 0 for r in rows), 0),
        "paint_ltr":     round(sum(r.paint_ltr     or 0 for r in rows), 1),
        "tiles_sqm":     round(sum(r.tiles_sqm     or 0 for r in rows), 2),
    }
    chart_data = [
        {"material": "Cement",    "unit": "bags", "quantity": totals["cement_bags"]},
        {"material": "Sand",      "unit": "CFT",  "quantity": totals["sand_cft"]},
        {"material": "Aggregate", "unit": "CFT",  "quantity": totals["aggregate_cft"]},
        {"material": "Steel",     "unit": "kg",   "quantity": totals["steel_kg"]},
        {"material": "Bricks",    "unit": "nos",  "quantity": totals["bricks_nos"]},
        {"material": "Paint",     "unit": "ltr",  "quantity": totals["paint_ltr"]},
        {"material": "Tiles",     "unit": "m2",   "quantity": totals["tiles_sqm"]},
    ]
    return {"totals": totals, "chart_data": chart_data}


@router.get("/cost-distribution/{project_id}", summary="Cost breakdown for a project")
def cost_distribution(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Ownership check
    from app.crud import project as project_crud
    p = project_crud.get_project_by_id(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        if str(p.created_by) != str(current_user.id):
            raise HTTPException(status_code=403, detail="You do not have access to this project")

    estimates = db.query(Estimate).filter(Estimate.project_id == str(project_id)).all()
    if not estimates:
        return {"message": "No estimates found. Run estimation first.", "data": [], "total_cost": 0}

    work_costs: dict = {}
    for e in estimates:
        label = e.work_type.value.replace("_", " ").title() if hasattr(e.work_type, 'value') else str(e.work_type).replace("_", " ").title()
        work_costs[label] = work_costs.get(label, 0) + (e.total_cost or 0)

    total = sum(work_costs.values())
    return {
        "total_cost": round(total, 2),
        "data": [
            {
                "name":       k,
                "value":      round(v, 2),
                "percentage": round(v / total * 100, 1) if total > 0 else 0,
            }
            for k, v in sorted(work_costs.items(), key=lambda x: -x[1])
        ],
    }


@router.get("/project-comparison", summary="Compare multiple projects")
def project_comparison(
    project_ids: str = Query(..., description="Comma-separated project UUIDs"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        ids = [str(UUID(pid.strip())) for pid in project_ids.split(",") if pid.strip()]
    except ValueError:
        return []
    projects = db.query(Project).filter(Project.id.in_(ids)).all()
    # Filter to only projects the caller is authorized to see
    if current_user.role not in (UserRole.ADMIN, UserRole.PROJECT_MANAGER):
        projects = [p for p in projects if str(p.created_by) == str(current_user.id)]
    result = []
    for p in projects:
        estimates = db.query(Estimate).filter(Estimate.project_id == str(p.id)).all()
        result.append({
            "project_id":        str(p.id),
            "project_code":      p.project_code,
            "project_name":      p.project_name,
            "building_type":     p.building_type.value if hasattr(p.building_type, 'value') else str(p.building_type),
            "num_floors":        p.num_floors,
            "total_area_m2":     p.total_built_up_area or 0,
            "estimated_cost":    p.total_estimated_cost or 0,
            "cost_per_m2":       round((p.total_estimated_cost or 0) / max(p.total_built_up_area or 1, 1), 2),
            "total_cement_bags": round(sum(e.cement_bags or 0 for e in estimates), 1),
            "total_steel_kg":    round(sum(e.steel_kg or 0 for e in estimates), 1),
        })
    return result


@router.get("/material-rates/{material_id}", summary="Rate trend for a material")
def material_rate_trend(
    material_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    history = (
        db.query(MaterialRateHistory)
        .filter(MaterialRateHistory.material_id == str(material_id))
        .order_by(MaterialRateHistory.changed_at.asc())
        .all()
    )
    return [
        {
            "date":       h.changed_at.strftime("%d %b %Y"),
            "old_rate":   h.old_rate,
            "new_rate":   h.new_rate,
            "change":     round(h.new_rate - h.old_rate, 2),
            "change_pct": round((h.new_rate - h.old_rate) / h.old_rate * 100, 1) if h.old_rate else 0,
        }
        for h in history
    ]


@router.get("/quantity-comparison", summary="Quantity comparison across projects")
def quantity_comparison(
    work_type: WorkType = Query(WorkType.RCC_SLAB),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    rows = (
        db.query(Project.project_code, Project.project_name, Estimate.quantity, Estimate.unit)
        .join(Estimate, Estimate.project_id == Project.id)
        .filter(Estimate.work_type == work_type)
        .order_by(Estimate.quantity.desc())
        .limit(20)
        .all()
    )
    return {
        "work_type": work_type.value if hasattr(work_type, 'value') else str(work_type),
        "data": [
            {"project_code": r[0], "project_name": r[1], "quantity": round(r[2], 3), "unit": r[3]}
            for r in rows
        ],
    }
