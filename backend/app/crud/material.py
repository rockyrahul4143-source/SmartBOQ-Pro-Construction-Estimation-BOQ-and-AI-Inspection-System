from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from datetime import datetime

from app.models.material import Material, MaterialCategory, MaterialUnit, MaterialRateHistory
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialRateUpdate


def _generate_code(db: Session, category: MaterialCategory) -> str:
    prefix = {
        MaterialCategory.CEMENT: "CEM", MaterialCategory.AGGREGATE: "AGG",
        MaterialCategory.SAND: "SND", MaterialCategory.STEEL: "STL",
        MaterialCategory.BRICK: "BRK", MaterialCategory.BLOCK: "BLK",
        MaterialCategory.PAINT: "PNT", MaterialCategory.TILE: "TIL",
        MaterialCategory.WATERPROOFING: "WPF", MaterialCategory.WOOD: "WOD",
        MaterialCategory.GLASS: "GLS", MaterialCategory.ELECTRICAL: "ELC",
        MaterialCategory.PLUMBING: "PLB", MaterialCategory.OTHER: "OTH",
    }.get(category, "MAT")
    count = db.query(func.count(Material.id)).scalar() + 1
    code = f"{prefix}-{count:04d}"
    while db.query(Material).filter(Material.material_code == code).first():
        count += 1
        code = f"{prefix}-{count:04d}"
    return code


def get_material_by_id(db: Session, material_id: UUID) -> Optional[Material]:
    return db.query(Material).filter(Material.id == str(material_id)).first()


def get_material_by_code(db: Session, code: str) -> Optional[Material]:
    return db.query(Material).filter(Material.material_code == code).first()


def get_materials(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    category: Optional[MaterialCategory] = None,
    search: Optional[str] = None,
    active_only: bool = True,
) -> Tuple[List[Material], int]:
    q = db.query(Material)
    if active_only:
        q = q.filter(Material.is_active == True)
    if category:
        q = q.filter(Material.category == category)
    if search:
        pattern = f"%{search}%"
        q = q.filter(or_(Material.name.ilike(pattern), Material.material_code.ilike(pattern)))
    total = q.count()
    return q.order_by(Material.category, Material.name).offset(skip).limit(limit).all(), total


def create_material(db: Session, payload: MaterialCreate) -> Material:
    code = payload.material_code or _generate_code(db, payload.category)
    material = Material(
        material_code=code,
        name=payload.name,
        category=payload.category,
        unit=payload.unit,
        current_rate=payload.current_rate,
        supplier_name=payload.supplier_name,
        supplier_contact=payload.supplier_contact,
        description=payload.description,
        is_active=True,
        last_updated=datetime.utcnow(),
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def update_material(db: Session, material: Material, payload: MaterialUpdate) -> Material:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    material.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(material)
    return material


def update_rate(db: Session, material: Material, payload: MaterialRateUpdate, changed_by: UUID) -> Material:
    history = MaterialRateHistory(
        material_id=str(material.id),
        old_rate=material.current_rate,
        new_rate=payload.new_rate,
        changed_by=str(changed_by),
        notes=payload.notes,
    )
    db.add(history)
    material.current_rate = payload.new_rate
    material.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(material)
    return material


def get_rate_history(db: Session, material_id: UUID) -> List[MaterialRateHistory]:
    return (
        db.query(MaterialRateHistory)
        .filter(MaterialRateHistory.material_id == str(material_id))
        .order_by(MaterialRateHistory.changed_at.desc())
        .all()
    )


def delete_material(db: Session, material: Material) -> None:
    material.is_active = False
    db.commit()


def get_materials_by_category(db: Session) -> dict:
    result = {}
    for cat in MaterialCategory:
        mats = db.query(Material).filter(
            Material.category == cat, Material.is_active == True
        ).order_by(Material.name).all()
        if mats:
            result[cat.value] = mats
    return result
