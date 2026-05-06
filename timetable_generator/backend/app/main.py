"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, health, teachers, subjects, classes, rooms, periods, timetables
from app.routers import sync
from app.routers import schools


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    print("🚀 Timetable backend started")
    # NOTE: Tables are managed via Alembic migrations, NOT created here.
    # Calling engine.begin() at startup on Neon causes DNS/SSL failures
    # on Python 3.14 before the event loop is fully initialised.
    # Run: alembic upgrade head   — to apply migrations instead.
    yield
    print("Shutting down...")
    await engine.dispose()


app = FastAPI(
    title="Smart Timetable Generator API",
    description="Backend API for Migrant Model Secondary School Timetable System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,     prefix="/api/v1",      tags=["health"])
app.include_router(auth.router,       prefix="/api/v1/auth", tags=["authentication"])
app.include_router(teachers.router,   prefix="/api/v1",      tags=["teachers"])
app.include_router(subjects.router,   prefix="/api/v1",      tags=["subjects"])
app.include_router(classes.router,    prefix="/api/v1",      tags=["classes"])
app.include_router(rooms.router,      prefix="/api/v1",      tags=["rooms"])
app.include_router(periods.router,    prefix="/api/v1",      tags=["periods"])
app.include_router(timetables.router, prefix="/api/v1",      tags=["timetables"])
app.include_router(sync.router,       prefix="/api/v1",      tags=["sync"])
app.include_router(schools.router,    prefix="/api/v1",      tags=["schools"])


@app.get("/")
async def root():
    return {
        "message": "Welcome to Smart Timetable Generator API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "An internal server error occurred",
                 "detail": str(exc)},
    )