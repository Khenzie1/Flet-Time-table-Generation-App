"""Period schemas."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import time, datetime


class PeriodBase(BaseModel):
    """Base period schema."""
    period_number: int = Field(..., ge=1, le=10)
    start_time: time
    end_time: time
    is_break: bool = False
    day_of_week: str = Field(..., pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday)$")


class PeriodCreate(PeriodBase):
    """Period creation schema."""
    school_id: str


class PeriodUpdate(BaseModel):
    """Period update schema."""
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_break: Optional[bool] = None


class PeriodResponse(PeriodBase):
    """Period response schema."""
    id: str
    school_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True