import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.base_uuid import GUID


class Building(Base):
    __tablename__ = "buildings"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    project_id = Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    building_name = Column(String(255), nullable=False, default="Main Building")
    num_floors = Column(Integer, nullable=False, default=1)
    plot_length = Column(Float, nullable=True)
    plot_width = Column(Float, nullable=True)
    excavation_depth = Column(Float, nullable=True, default=1.5)
    footing_length = Column(Float, nullable=True, default=1.2)
    footing_width = Column(Float, nullable=True, default=1.2)
    footing_depth = Column(Float, nullable=True, default=0.3)
    num_footings = Column(Integer, nullable=True, default=0)
    pcc_thickness = Column(Float, nullable=True, default=0.075)
    column_length = Column(Float, nullable=True, default=0.3)
    column_width = Column(Float, nullable=True, default=0.3)
    floor_height = Column(Float, nullable=True, default=3.0)
    num_columns = Column(Integer, nullable=True, default=0)
    beam_width = Column(Float, nullable=True, default=0.23)
    beam_depth = Column(Float, nullable=True, default=0.45)
    total_beam_length = Column(Float, nullable=True, default=0.0)
    slab_length = Column(Float, nullable=True)
    slab_width = Column(Float, nullable=True)
    slab_thickness = Column(Float, nullable=True, default=0.125)
    wall_thickness_external = Column(Float, nullable=True, default=0.23)
    wall_thickness_internal = Column(Float, nullable=True, default=0.115)
    total_external_wall_length = Column(Float, nullable=True, default=0.0)
    total_internal_wall_length = Column(Float, nullable=True, default=0.0)
    wall_height = Column(Float, nullable=True, default=3.0)
    plaster_thickness_external = Column(Float, nullable=True, default=0.020)
    plaster_thickness_internal = Column(Float, nullable=True, default=0.012)
    flooring_type = Column(String(100), nullable=True, default="tiles")
    tile_size = Column(Float, nullable=True, default=0.6)
    tile_wastage_pct = Column(Float, nullable=True, default=10.0)
    paint_coats = Column(Integer, nullable=True, default=2)
    num_doors = Column(Integer, nullable=True, default=0)
    door_width = Column(Float, nullable=True, default=0.9)
    door_height = Column(Float, nullable=True, default=2.1)
    num_windows = Column(Integer, nullable=True, default=0)
    window_width = Column(Float, nullable=True, default=1.2)
    window_height = Column(Float, nullable=True, default=1.2)
    steel_percentage_slab = Column(Float, nullable=True, default=1.0)
    steel_percentage_column = Column(Float, nullable=True, default=2.5)
    steel_percentage_beam = Column(Float, nullable=True, default=2.0)
    waterproofing_area = Column(Float, nullable=True, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="buildings")
    rooms = relationship("Room", back_populates="building", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    building_id = Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    floor_number = Column(Integer, nullable=False, default=0)
    room_name = Column(String(255), nullable=False)
    length = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=True)
    area = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    building = relationship("Building", back_populates="rooms")
