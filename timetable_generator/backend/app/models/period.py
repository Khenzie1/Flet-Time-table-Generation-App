"""Period model."""
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Time
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class Period(Base):
    """Period model for daily schedule configuration."""
    
    __tablename__ = "periods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False)
    period_number = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_break = Column(Boolean, default=False)
    day_of_week = Column(String(10), nullable=False)  # Monday, Tuesday, etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Period {self.period_number} on {self.day_of_week}>"