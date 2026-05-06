"""Subject model."""
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from app.database import Base


class SubjectCategory(str, enum.Enum):
    """Subject category enumeration."""
    CORE = "Core"
    ELECTIVE = "Elective"
    PRACTICAL = "Practical"


class Subject(Base):
    """Subject model."""
    
    __tablename__ = "subjects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(SQLEnum(SubjectCategory), nullable=False)
    periods_per_week = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, default=40)
    requires_lab = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    teachers = relationship("TeacherSubject", back_populates="subject")
    class_subjects = relationship("ClassSubject", back_populates="subject")
    
    def __repr__(self):
        return f"<Subject {self.code}: {self.name}>"