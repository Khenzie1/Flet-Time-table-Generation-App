"""Routers package."""
from app.routers import auth, health, teachers, subjects, classes, rooms, periods, timetables

__all__ = [
    "auth",
    "health",
    "teachers",
    "subjects",
    "classes",
    "rooms",
    "periods",
    "timetables"
]