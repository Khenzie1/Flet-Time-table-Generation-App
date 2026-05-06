"""Room model."""
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from app.database import Base


class RoomType(str, enum.Enum):
    """Room type enumeration."""
    REGULAR = "Regular"
    LAB = "Lab"
    WORKSHOP = "Workshop"
    HALL = "Hall"


class Room(Base):
    """Room model."""
    
    __tablename__ = "rooms"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    room_code = Column(String(20), nullable=False)
    room_name = Column(String(255), nullable=False)
    capacity = Column(Integer, nullable=False)
    room_type = Column(SQLEnum(RoomType), nullable=False)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    unavailability = relationship("RoomUnavailability", back_populates="room", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Room {self.room_code}: {self.room_name}>"


class RoomUnavailability(Base):
    """Room unavailability periods."""
    
    __tablename__ = "rooms_unavailability"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False)
    day_of_week = Column(String(10), nullable=False)
    period_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    room = relationship("Room", back_populates="unavailability")