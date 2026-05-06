"""School schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class SchoolBase(BaseModel):
    """Base school schema."""
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    config_json: Optional[Dict] = {}


class SchoolCreate(SchoolBase):
    """School creation schema."""
    pass


class SchoolUpdate(BaseModel):
    """School update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    config_json: Optional[Dict] = None


class SchoolResponse(SchoolBase):
    """School response schema."""
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True