"""Timetable models."""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum as SQLEnum, Time, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from app.database import Base


class TimetableType(str, enum.Enum):
    """Timetable type enumeration."""
    CLASS = "Class"
    EXAM = "Exam"


class TimetableStatus(str, enum.Enum):
    """Timetable status enumeration."""
    DRAFT = "Draft"
    APPROVED = "Approved"
    PUBLISHED = "Published"


class Timetable(Base):
    """Timetable model."""
    
    __tablename__ = "timetables"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(SQLEnum(TimetableType), nullable=False)
    term = Column(String(50))
    academic_year = Column(String(20))
    status = Column(SQLEnum(TimetableStatus), default=TimetableStatus.DRAFT)
    version = Column(Integer, default=1)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    slots = relationship("TimetableSlot", back_populates="timetable", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class TimetableSlot(Base):
    """Timetable slot model."""
    
    __tablename__ = "timetable_slots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timetable_id = Column(UUID(as_uuid=True), ForeignKey("timetables.id"), nullable=False)
    day_of_week = Column(String(10), nullable=False)
    period_number = Column(Integer, nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False)
    start_time = Column(Time)
    end_time = Column(Time)
    
    # Relationships
    timetable = relationship("Timetable", back_populates="slots")
    class_obj = relationship("Class")
    subject = relationship("Subject")
    teacher = relationship("Teacher")
    room = relationship("Room")