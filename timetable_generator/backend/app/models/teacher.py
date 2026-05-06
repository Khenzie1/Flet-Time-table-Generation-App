"""Teacher model."""
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base


class Teacher(Base):
    """Teacher model."""
    
    __tablename__ = "teachers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    teacher_code = Column(String(20), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255))
    max_daily_periods = Column(Integer, default=6)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subjects = relationship("TeacherSubject", back_populates="teacher", cascade="all, delete-orphan")
    unavailability = relationship("TeacherUnavailability", back_populates="teacher", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Teacher {self.teacher_code}: {self.full_name}>"


class TeacherSubject(Base):
    """Teacher-Subject association model."""
    
    __tablename__ = "teacher_subjects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    teacher = relationship("Teacher", back_populates="subjects")
    subject = relationship("Subject")


class TeacherUnavailability(Base):
    """Teacher unavailability periods."""
    
    __tablename__ = "teacher_unavailability"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    day_of_week = Column(String(10), nullable=False)  # Monday, Tuesday, etc.
    period_number = Column(Integer, nullable=False)
    reason = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    teacher = relationship("Teacher", back_populates="unavailability")