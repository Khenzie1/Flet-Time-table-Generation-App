"""Timetable routes."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Dict, Any
import uuid
import asyncio

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.timetable import Timetable, TimetableSlot, TimetableStatus
from app.models.user import User
from app.schemas.timetable import (
    TimetableCreate, TimetableUpdate, TimetableResponse,
    TimetableSlotUpdate, TimetableSlotResponse,
    TimetableGenerationRequest, TimetableGenerationStatus,
    TimetableValidationResult
)
from app.services.timetable_generator import TimetableGenerator
from app.services.export_service import ExportService

router = APIRouter(prefix="/timetables", tags=["timetables"])

# Store generation tasks and cancellation flags
generation_tasks: Dict[str, Dict[str, Any]] = {}


@router.post("", response_model=TimetableResponse)
async def create_timetable(
    timetable_data: TimetableCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    data = timetable_data.model_dump()
    data["created_by"] = current_user.id
    data["school_id"] = current_user.school_id
    db_timetable = Timetable(**data)
    db.add(db_timetable)
    await db.commit()
    await db.refresh(db_timetable)
    return TimetableResponse.model_validate(db_timetable)


@router.get("", response_model=List[TimetableResponse])
async def list_timetables(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[TimetableStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    query = select(Timetable).where(Timetable.school_id == current_user.school_id)
    if status:
        query = query.where(Timetable.status == status)
    query = query.offset(skip).limit(limit).order_by(Timetable.created_at.desc())
    result = await db.execute(query)
    timetables = result.scalars().all()
    return [TimetableResponse.model_validate(t) for t in timetables]


@router.get("/{timetable_id}", response_model=TimetableResponse)
async def get_timetable(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    result = await db.execute(
        select(Timetable).where(
            and_(
                Timetable.id == timetable_id,
                Timetable.school_id == current_user.school_id
            )
        )
    )
    timetable = result.scalar_one_or_none()
    if not timetable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable not found")
    return TimetableResponse.model_validate(timetable)


@router.post("/generate", response_model=TimetableGenerationStatus)
async def generate_timetable(
    request: TimetableGenerationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    task_id = str(uuid.uuid4())
    generation_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Initializing generation...",
        "timetable_id": None,
        "cancelled": False          # ← added cancellation flag
    }
    background_tasks.add_task(
        run_timetable_generation,
        task_id,
        request,
        current_user,
        db
    )
    return TimetableGenerationStatus(
        status="pending",
        progress=0,
        message="Generation started",
        timetable_id=None
    )


@router.get("/generation/{task_id}/status", response_model=TimetableGenerationStatus)
async def get_generation_status(
    task_id: str,
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    if task_id not in generation_tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task = generation_tasks[task_id]
    return TimetableGenerationStatus(
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        timetable_id=task.get("timetable_id")
    )


@router.post("/generation/{task_id}/stop", response_model=Dict[str, str])
async def stop_generation(
    task_id: str,
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Stop a running generation task."""
    if task_id not in generation_tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task = generation_tasks[task_id]
    if task["status"] not in ["running", "pending"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task is not running")
    # Set cancellation flag
    task["cancelled"] = True
    task["status"] = "cancelled"
    task["message"] = "Generation cancelled by user"
    return {"message": "Cancellation requested"}


@router.get("/{timetable_id}/validate", response_model=TimetableValidationResult)
async def validate_timetable(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    result = await db.execute(
        select(Timetable).where(
            and_(
                Timetable.id == timetable_id,
                Timetable.school_id == current_user.school_id
            )
        )
    )
    timetable = result.scalar_one_or_none()
    if not timetable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable not found")
    generator = TimetableGenerator(db)
    conflicts = await generator.validate_timetable(timetable_id)
    return TimetableValidationResult(
        is_valid=len(conflicts) == 0,
        conflicts=conflicts,
        warnings=[]
    )


@router.put("/{timetable_id}/slots/{slot_id}", response_model=TimetableSlotResponse)
async def update_timetable_slot(
    timetable_id: str,
    slot_id: str,
    slot_data: TimetableSlotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    result = await db.execute(
        select(TimetableSlot).where(
            and_(
                TimetableSlot.id == slot_id,
                TimetableSlot.timetable_id == timetable_id
            )
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    update_data = slot_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(slot, field, value)
    await db.commit()
    await db.refresh(slot)
    return TimetableSlotResponse.model_validate(slot)


@router.post("/{timetable_id}/publish", response_model=TimetableResponse)
async def publish_timetable(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    result = await db.execute(
        select(Timetable).where(
            and_(
                Timetable.id == timetable_id,
                Timetable.school_id == current_user.school_id
            )
        )
    )
    timetable = result.scalar_one_or_none()
    if not timetable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable not found")
    generator = TimetableGenerator(db)
    conflicts = await generator.validate_timetable(timetable_id)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish timetable with {len(conflicts)} conflicts"
        )
    timetable.status = TimetableStatus.PUBLISHED
    timetable.version += 1
    await db.commit()
    await db.refresh(timetable)
    return TimetableResponse.model_validate(timetable)


@router.get("/{timetable_id}/export")
async def export_timetable(
    timetable_id: str,
    format: str = Query("xlsx", regex="^(csv|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    result = await db.execute(
        select(Timetable).where(
            and_(
                Timetable.id == timetable_id,
                Timetable.school_id == current_user.school_id
            )
        )
    )
    timetable = result.scalar_one_or_none()
    if not timetable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timetable not found")
    export_service = ExportService(db)
    if format == "csv":
        return await export_service.export_to_csv(timetable_id)
    else:
        return await export_service.export_to_excel(timetable_id)


async def run_timetable_generation(
    task_id: str,
    request: TimetableGenerationRequest,
    current_user: User,
    db: AsyncSession
):
    """Run timetable generation in background, checking for cancellation."""
    try:
        task = generation_tasks[task_id]
        task["status"] = "running"
        task["message"] = "Loading data..."

        # Check cancellation
        if task["cancelled"]:
            return

        # Initialize generator
        generator = TimetableGenerator(db)

        task["progress"] = 20
        task["message"] = "Building constraints..."
        if task["cancelled"]:
            return

        # Define a progress callback that checks cancellation
        def progress_callback(progress: int, message: str):
            if task["cancelled"]:
                raise asyncio.CancelledError("Generation cancelled")
            task["progress"] = progress
            task["message"] = message

        # Generate timetable
        timetable_id = await generator.generate(
            school_id=request.school_id,
            term=request.term,
            academic_year=request.academic_year,
            parameters=request.parameters,
            progress_callback=progress_callback
        )

        task["status"] = "completed"
        task["progress"] = 100
        task["message"] = "Generation complete"
        task["timetable_id"] = str(timetable_id)

    except asyncio.CancelledError:
        # Generation was cancelled
        generation_tasks[task_id]["status"] = "cancelled"
        generation_tasks[task_id]["message"] = "Generation cancelled"
    except Exception as e:
        generation_tasks[task_id]["status"] = "failed"
        generation_tasks[task_id]["message"] = f"Generation failed: {str(e)}"
        generation_tasks[task_id]["progress"] = 0