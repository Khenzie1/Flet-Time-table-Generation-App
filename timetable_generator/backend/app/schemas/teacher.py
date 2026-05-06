"""Teacher schemas."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class TeacherBase(BaseModel):
    """Base teacher schema."""
    teacher_code: str = Field(..., min_length=1, max_length=20)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    max_daily_periods: int = Field(6, ge=1, le=10)
    is_active: bool = True


class TeacherCreate(TeacherBase):
    """Teacher creation schema."""
    school_id: Optional[str] = None   # injected by crud_base from DB if omitted
    subject_ids: Optional[List[str]] = []


class TeacherUpdate(BaseModel):
    """Teacher update schema."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    max_daily_periods: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None
    subject_ids: Optional[List[str]] = None


class TeacherUnavailabilityBase(BaseModel):
    """Teacher unavailability base schema."""
    day_of_week: str
    period_number: int
    reason: Optional[str] = None


class TeacherUnavailabilityCreate(TeacherUnavailabilityBase):
    """Teacher unavailability creation schema."""
    teacher_id: str


class TeacherUnavailabilityResponse(TeacherUnavailabilityBase):
    """Teacher unavailability response schema."""
    id: str
    teacher_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherResponse(TeacherBase):
    """Teacher response schema."""
    id: str
    school_id: str
    subject_ids: List[str] = []
    unavailability: List[TeacherUnavailabilityResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeacherBulkImport(BaseModel):
    """Teacher bulk import schema."""
    teachers: List[TeacherCreate]