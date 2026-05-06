"""Timetable schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, time


class TimetableBase(BaseModel):
    """Base timetable schema."""
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(Class|Exam)$")
    term: Optional[str] = Field(None, max_length=50)
    academic_year: Optional[str] = Field(None, max_length=20)
    status: str = Field("Draft", pattern="^(Draft|Approved|Published)$")


class TimetableCreate(TimetableBase):
    """Timetable creation schema."""
    school_id: str


class TimetableUpdate(BaseModel):
    """Timetable update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern="^(Draft|Approved|Published)$")
    term: Optional[str] = None
    academic_year: Optional[str] = None


class TimetableSlotBase(BaseModel):
    """Timetable slot base schema."""
    day_of_week: str = Field(..., pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday)$")
    period_number: int = Field(..., ge=1, le=10)
    class_id: str
    subject_id: str
    teacher_id: str
    room_id: str
    start_time: Optional[time] = None
    end_time: Optional[time] = None


class TimetableSlotCreate(TimetableSlotBase):
    """Timetable slot creation schema."""
    timetable_id: str


class TimetableSlotUpdate(BaseModel):
    """Timetable slot update schema."""
    subject_id: Optional[str] = None
    teacher_id: Optional[str] = None
    room_id: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None


class TimetableSlotResponse(TimetableSlotBase):
    """Timetable slot response schema."""
    id: str
    timetable_id: str

    class Config:
        from_attributes = True


class TimetableResponse(TimetableBase):
    """Timetable response schema."""
    id: str
    school_id: str
    version: int
    created_by: str
    slots: List[TimetableSlotResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimetableGenerationRequest(BaseModel):
    """Timetable generation request schema."""
    type: str = "Class"
    term: str
    academic_year: str
    school_id: str
    parameters: Optional[Dict[str, Any]] = {}


class TimetableGenerationStatus(BaseModel):
    """Timetable generation status schema."""
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    message: str
    timetable_id: Optional[str] = None
    conflicts: Optional[List[Dict[str, Any]]] = None


class TimetableValidationResult(BaseModel):
    """Timetable validation result schema."""
    is_valid: bool
    conflicts: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]