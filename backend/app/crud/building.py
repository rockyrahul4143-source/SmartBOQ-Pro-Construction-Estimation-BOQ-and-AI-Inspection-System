from typing import Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.building import Building, Room
from app.schemas.building import BuildingCreate, BuildingUpdate, RoomCreate


def get_building_by_id(db: Session, building_id: UUID) -> Optional[Building]:
    return db.query(Building).filter(Building.id == str(building_id)).first()


def get_buildings_by_project(db: Session, project_id: UUID) -> List[Building]:
    return db.query(Building).filter(Building.project_id == str(project_id)).all()


def create_building(db: Session, payload: BuildingCreate) -> Building:
    data = payload.model_dump()
    data["project_id"] = str(data["project_id"])
    building = Building(**data)
    if not building.slab_length and building.plot_length:
        building.slab_length = building.plot_length
    if not building.slab_width and building.plot_width:
        building.slab_width = building.plot_width
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


def update_building(db: Session, building: Building, payload: BuildingUpdate) -> Building:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(building, field, value)
    if not building.slab_length and building.plot_length:
        building.slab_length = building.plot_length
    if not building.slab_width and building.plot_width:
        building.slab_width = building.plot_width
    db.commit()
    db.refresh(building)
    return building


def delete_building(db: Session, building: Building) -> None:
    db.delete(building)
    db.commit()


def get_rooms_by_building(db: Session, building_id: UUID) -> List[Room]:
    return db.query(Room).filter(Room.building_id == str(building_id)).order_by(
        Room.floor_number, Room.room_name
    ).all()


def create_room(db: Session, building_id: UUID, payload: RoomCreate) -> Room:
    # Exclude 'area' from model_dump to avoid duplicate keyword if schema has it
    data = {k: v for k, v in payload.model_dump().items() if k != "area"}
    room = Room(
        building_id=str(building_id),
        area=round(payload.length * payload.width, 4),
        **data,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: UUID) -> bool:
    room = db.query(Room).filter(Room.id == str(room_id)).first()
    if not room:
        return False
    db.delete(room)
    db.commit()
    return True
