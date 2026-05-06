"""Room schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RoomBase(BaseModel):
    """Base room schema."""
    room_code: str = Field(..., min_length=1, max_length=20)
    room_name: str = Field(..., min_length=1, max_length=255)
    capacity: int = Field(..., ge=1)
    room_type: str = Field(..., pattern="^(Regular|Lab|Workshop|Hall)$")
    is_available: bool = True


class RoomCreate(RoomBase):
    """Room creation schema."""
    school_id: str


class RoomUpdate(BaseModel):
    """Room update schema."""
    room_name: Optional[str] = Field(None, min_length=1, max_length=255)
    capacity: Optional[int] = Field(None, ge=1)
    room_type: Optional[str] = Field(None, pattern="^(Regular|Lab|Workshop|Hall)$")
    is_available: Optional[bool] = None


class RoomUnavailabilityBase(BaseModel):
    """Room unavailability base schema."""
    day_of_week: str
    period_number: int


class RoomUnavailabilityCreate(RoomUnavailabilityBase):
    """Room unavailability creation schema."""
    room_id: str


class RoomUnavailabilityResponse(RoomUnavailabilityBase):
    """Room unavailability response schema."""
    id: str
    room_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoomResponse(RoomBase):
    """Room response schema."""
    id: str
    school_id: str
    unavailability: List[RoomUnavailabilityResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True