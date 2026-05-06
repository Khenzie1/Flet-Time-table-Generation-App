"""Models package."""
from app.database import Base

# Import all models
from app.models.user import User
from app.models.school import School
from app.models.teacher import Teacher, TeacherSubject, TeacherUnavailability
from app.models.subject import Subject
from app.models.class_ import Class, ClassSubject
from app.models.room import Room, RoomUnavailability
from app.models.period import Period
from app.models.timetable import Timetable, TimetableSlot
from app.models.sync import SyncQueue, AuditLog

__all__ = [
    "Base",
    "User",
    "School",
    "Teacher",
    "TeacherSubject",
    "TeacherUnavailability",
    "Subject",
    "Class",
    "ClassSubject",
    "Room",
    "RoomUnavailability",
    "Period",
    "Timetable",
    "TimetableSlot",
    "SyncQueue",
    "AuditLog"
]