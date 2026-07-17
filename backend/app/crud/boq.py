from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from datetime import datetime

from app.models.boq import BOQ, BOQItem, BOQStatus
from app.models.estimate import Estimate, WorkType
from app.schemas.boq import BOQCreate, BOQUpdate, BOQItemCreate, BOQItemUpdate


def _boq_number(db: Session, project_id) -> str:
    count = db.query(func.count(BOQ.id)).filter(BOQ.project_id == str(project_id)).scalar()
    pid_short = str(project_id)[:8].upper()
    return f"BOQ-{pid_short}-{count + 1:02d}"


def get_boq_by_id(db: Session, boq_id: UUID) -> Optional[BOQ]:
    return db.query(BOQ).filter(BOQ.id == str(boq_id)).first()


def get_boqs_by_project(db: Session, project_id: UUID) -> List[BOQ]:
    return db.query(BOQ).filter(BOQ.project_id == str(project_id)).order_by(BOQ.created_at.desc()).all()


def create_boq(db: Session, payload: BOQCreate, prepared_by: UUID) -> BOQ:
    boq = BOQ(
        project_id=str(payload.project_id),
        boq_number=_boq_number(db, payload.project_id),
        title=payload.title,
        overhead_pct=payload.overhead_pct,
        profit_pct=payload.profit_pct,
        contingency_pct=payload.contingency_pct,
        currency=payload.currency,
        notes=payload.notes,
        prepared_by=str(prepared_by),
        status=BOQStatus.DRAFT,
    )
    db.add(boq)
    db.commit()
    db.refresh(boq)
    return boq


def update_boq(db: Session, boq: BOQ, payload: BOQUpdate) -> BOQ:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(boq, field, value)
    _recalculate_totals(db, boq)
    db.commit()
    db.refresh(boq)
    return boq


def delete_boq(db: Session, boq: BOQ) -> None:
    db.delete(boq)
    db.commit()


def approve_boq(db: Session, boq: BOQ, approver_id: UUID) -> BOQ:
    boq.status = BOQStatus.APPROVED
    boq.approved_by = str(approver_id)
    boq.approval_date = datetime.utcnow()
    db.commit()
    db.refresh(boq)
    return boq


def auto_generate_from_estimates(db: Session, boq: BOQ) -> BOQ:
    estimates = db.query(Estimate).filter(
        Estimate.project_id == str(boq.project_id)
    ).order_by(Estimate.work_type).all()

    db.query(BOQItem).filter(BOQItem.boq_id == str(boq.id)).delete(synchronize_session=False)

    DESCRIPTIONS = {
        WorkType.EXCAVATION:          ("Earth Excavation in Foundation", "m3"),
        WorkType.PCC:                 ("Plain Cement Concrete (M10) in Foundation", "m3"),
        WorkType.RCC_FOOTING:         ("RCC Isolated Footing (M20)", "m3"),
        WorkType.RCC_COLUMN:          ("RCC Columns (M20)", "m3"),
        WorkType.RCC_BEAM:            ("RCC Beams (M20)", "m3"),
        WorkType.RCC_SLAB:            ("RCC Roof/Floor Slab (M20)", "m3"),
        WorkType.BRICKWORK:           ("Brickwork in CM 1:6 (9-inch wall)", "m3"),
        WorkType.BLOCKWORK:           ("Block Masonry in CM 1:4", "m3"),
        WorkType.PLASTER_EXTERNAL:    ("External Cement Plaster 1:6, 20mm thick", "m2"),
        WorkType.PLASTER_INTERNAL:    ("Internal Cement Plaster 1:4, 12mm thick", "m2"),
        WorkType.FLOORING:            ("Floor Tiling with CM bedding 1:4", "m2"),
        WorkType.TILING:              ("Wall Tiling with CM bedding 1:3", "m2"),
        WorkType.PAINT_INTERNAL:      ("Internal Emulsion Paint (2 coats + primer)", "m2"),
        WorkType.PAINT_EXTERNAL:      ("External Weather Coat Paint (2 coats)", "m2"),
        WorkType.STEEL_REINFORCEMENT: ("High Yield Deformed Steel Bars (HYSD)", "kg"),
        WorkType.WATERPROOFING:       ("Chemical Waterproofing Treatment", "m2"),
        WorkType.DOORS:               ("Solid Core Wooden Door with Frame", "no"),
        WorkType.WINDOWS:             ("Aluminum Sliding Window with Glass", "no"),
    }

    SECTIONS = {
        "A": ("SUBSTRUCTURE / EARTHWORK",    [WorkType.EXCAVATION, WorkType.PCC]),
        "B": ("REINFORCED CONCRETE WORKS",   [WorkType.RCC_FOOTING, WorkType.RCC_COLUMN, WorkType.RCC_BEAM, WorkType.RCC_SLAB]),
        "C": ("MASONRY WORKS",               [WorkType.BRICKWORK, WorkType.BLOCKWORK]),
        "D": ("PLASTERING & FINISHES",       [WorkType.PLASTER_EXTERNAL, WorkType.PLASTER_INTERNAL]),
        "E": ("FLOORING & TILING",           [WorkType.FLOORING, WorkType.TILING]),
        "F": ("PAINTING",                    [WorkType.PAINT_INTERNAL, WorkType.PAINT_EXTERNAL]),
        "G": ("STEEL REINFORCEMENT",         [WorkType.STEEL_REINFORCEMENT]),
        "H": ("WATERPROOFING",               [WorkType.WATERPROOFING]),
        "I": ("DOORS & WINDOWS",             [WorkType.DOORS, WorkType.WINDOWS]),
    }

    # Map work_type string or enum to estimate
    est_map = {}
    for e in estimates:
        key = e.work_type.value if hasattr(e.work_type, 'value') else str(e.work_type)
        est_map[key] = e

    items_to_add = []
    for sec_code, (sec_title, work_types) in SECTIONS.items():
        relevant = []
        for wt in work_types:
            wt_key = wt.value if hasattr(wt, 'value') else str(wt)
            if wt_key in est_map:
                relevant.append((wt, wt_key))
        if not relevant:
            continue

        items_to_add.append(BOQItem(
            boq_id=str(boq.id),
            item_no=sec_code,
            description=sec_title,
            unit="-", quantity=0, rate=0, amount=0,
            is_heading=True,
        ))
        for idx, (wt, wt_key) in enumerate(relevant, 1):
            e = est_map[wt_key]
            desc, unit = DESCRIPTIONS.get(wt, (wt_key.replace("_", " ").title(), "m3"))
            items_to_add.append(BOQItem(
                boq_id=str(boq.id),
                item_no=f"{sec_code}.{idx}",
                description=desc,
                unit=unit,
                quantity=round(e.quantity, 3),
                rate=0.0,
                amount=0.0,
                work_type=wt_key,
            ))

    db.add_all(items_to_add)
    db.commit()
    db.refresh(boq)
    return boq


def add_item(db: Session, boq_id: UUID, payload: BOQItemCreate) -> BOQItem:
    amount = round((payload.quantity or 0) * (payload.rate or 0), 2)
    data = payload.model_dump()
    data.pop("material_id", None)
    item = BOQItem(boq_id=str(boq_id), amount=amount, **data)
    db.add(item)
    db.commit()
    boq = db.query(BOQ).filter(BOQ.id == str(boq_id)).first()
    if boq:
        _recalculate_totals(db, boq)
    db.refresh(item)
    return item


def update_item(db: Session, item: BOQItem, payload: BOQItemUpdate) -> BOQItem:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.amount = round((item.quantity or 0) * (item.rate or 0), 2)
    db.commit()
    boq = db.query(BOQ).filter(BOQ.id == str(item.boq_id)).first()
    if boq:
        _recalculate_totals(db, boq)
    db.refresh(item)
    return item


def delete_item(db: Session, item: BOQItem) -> None:
    boq_id = str(item.boq_id)
    db.delete(item)
    db.commit()
    boq = db.query(BOQ).filter(BOQ.id == boq_id).first()
    if boq:
        _recalculate_totals(db, boq)


def _recalculate_totals(db: Session, boq: BOQ) -> None:
    items = db.query(BOQItem).filter(
        BOQItem.boq_id == str(boq.id), BOQItem.is_heading == False
    ).all()
    subtotal    = round(sum(i.amount or 0 for i in items), 2)
    overhead    = round(subtotal * (boq.overhead_pct    or 0) / 100, 2)
    profit      = round(subtotal * (boq.profit_pct      or 0) / 100, 2)
    contingency = round(subtotal * (boq.contingency_pct or 0) / 100, 2)
    grand       = round(subtotal + overhead + profit + contingency, 2)
    boq.subtotal           = subtotal
    boq.overhead_amount    = overhead
    boq.profit_amount      = profit
    boq.contingency_amount = contingency
    boq.grand_total        = grand
    db.commit()
