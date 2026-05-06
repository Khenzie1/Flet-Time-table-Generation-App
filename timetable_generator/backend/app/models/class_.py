"""Class model."""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from app.database import Base


class ClassLevel(str, enum.Enum):
    """Class level enumeration."""
    JSS1 = "JSS1"
    JSS2 = "JSS2"
    JSS3 = "JSS3"
    SS1 = "SS1"
    SS2 = "SS2"
    SS3 = "SS3"


class Class(Base):
    """Class model."""
    
    __tablename__ = "classes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    class_name = Column(String(50), unique=True, nullable=False)
    level = Column(SQLEnum(ClassLevel), nullable=False)
    student_count = Column(Integer, default=0)
    default_room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subjects = relationship("ClassSubject", back_populates="class_obj")
    default_room = relationship("Room", foreign_keys=[default_room_id])
    
    def __repr__(self):
        return f"<Class {self.class_name}>"


class ClassSubject(Base):
    """Class-Subject-Teacher association model."""
    
    __tablename__ = "class_subjects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    class_obj = relationship("Class", back_populates="subjects")
    subject = relationship("Subject")
    teacher = relationship("Teacher")