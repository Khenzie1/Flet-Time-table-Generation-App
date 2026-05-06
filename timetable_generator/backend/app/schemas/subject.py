"""Subject schemas."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SubjectBase(BaseModel):
    """Base subject schema."""
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., pattern="^(Core|Elective|Practical)$")
    periods_per_week: int = Field(..., ge=1, le=10)
    duration_minutes: int = Field(40, ge=30, le=120)
    requires_lab: bool = False


class SubjectCreate(SubjectBase):
    """Subject creation schema."""
    school_id: str


class SubjectUpdate(BaseModel):
    """Subject update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, pattern="^(Core|Elective|Practical)$")
    periods_per_week: Optional[int] = Field(None, ge=1, le=10)
    duration_minutes: Optional[int] = Field(None, ge=30, le=120)
    requires_lab: Optional[bool] = None


class SubjectResponse(SubjectBase):
    """Subject response schema."""
    id: str
    school_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True