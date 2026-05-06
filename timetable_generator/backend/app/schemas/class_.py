"""Class schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClassBase(BaseModel):
    """Base class schema."""
    class_name: str = Field(..., min_length=1, max_length=50)
    level: str = Field(..., pattern="^(JSS1|JSS2|JSS3|SS1|SS2|SS3)$")
    student_count: int = Field(0, ge=0)
    default_room_id: Optional[str] = None


class ClassCreate(ClassBase):
    """Class creation schema."""
    school_id: str


class ClassUpdate(BaseModel):
    """Class update schema."""
    class_name: Optional[str] = Field(None, min_length=1, max_length=50)
    student_count: Optional[int] = Field(None, ge=0)
    default_room_id: Optional[str] = None


class ClassSubjectBase(BaseModel):
    """Class subject base schema."""
    subject_id: str
    teacher_id: str


class ClassSubjectCreate(ClassSubjectBase):
    """Class subject creation schema."""
    class_id: str


class ClassSubjectResponse(ClassSubjectBase):
    """Class subject response schema."""
    id: str
    class_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ClassResponse(ClassBase):
    """Class response schema."""
    id: str
    school_id: str
    subjects: List[ClassSubjectResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True