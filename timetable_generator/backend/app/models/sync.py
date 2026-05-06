"""Sync and audit models."""
from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class SyncQueue(Base):
    """Sync queue model for tracking offline changes."""
    
    __tablename__ = "sync_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    operation = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    table_name = Column(String(50), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    data_json = Column(JSON)
    synced = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    """Audit log model."""
    
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    table_name = Column(String(50))
    record_id = Column(UUID(as_uuid=True))
    changes_json = Column(JSON)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)