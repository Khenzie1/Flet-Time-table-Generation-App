"""Teacher routes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import csv
import io
from typing import List
import uuid

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.teacher import Teacher, TeacherSubject, TeacherUnavailability
from app.models.user import User
from app.schemas.teacher import (
    TeacherCreate, TeacherUpdate, TeacherResponse,
    TeacherUnavailabilityCreate, TeacherUnavailabilityResponse,
    TeacherBulkImport
)
from app.routers.crud_base import create_crud_router

# Create base CRUD router
router = create_crud_router(
    model=Teacher,
    create_schema=TeacherCreate,
    update_schema=TeacherUpdate,
    response_schema=TeacherResponse,
    prefix="/teachers",
    tags=["teachers"]
)

# Additional teacher-specific endpoints


@router.post("/teachers/bulk-import", response_model=List[TeacherResponse])
async def bulk_import_teachers(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Bulk import teachers from CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be CSV"
        )
    
    # Read CSV file
    contents = await file.read()
    csv_file = io.StringIO(contents.decode('utf-8'))
    csv_reader = csv.DictReader(csv_file)
    
    created_teachers = []
    
    for row in csv_reader:
        # Check if teacher already exists
        existing = await db.execute(
            select(Teacher).where(
                or_(
                    Teacher.teacher_code == row['teacher_code'],
                    Teacher.email == row.get('email', '')
                )
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        # Create teacher
        teacher_data = {
            "school_id": current_user.school_id,
            "teacher_code": row['teacher_code'],
            "full_name": row['full_name'],
            "email": row.get('email'),
            "max_daily_periods": int(row.get('max_daily_periods', 6)),
            "is_active": row.get('is_active', 'true').lower() == 'true'
        }
        
        teacher = Teacher(**teacher_data)
        db.add(teacher)
        await db.flush()
        
        # Add subjects if specified
        if 'subjects' in row and row['subjects']:
            subject_ids = row['subjects'].split(';')
            for subject_id in subject_ids:
                teacher_subject = TeacherSubject(
                    teacher_id=teacher.id,
                    subject_id=uuid.UUID(subject_id.strip())
                )
                db.add(teacher_subject)
        
        created_teachers.append(teacher)
    
    await db.commit()
    
    # Refresh all teachers
    for teacher in created_teachers:
        await db.refresh(teacher)
    
    return [TeacherResponse.model_validate(t) for t in created_teachers]


@router.post("/teachers/{teacher_id}/unavailability", response_model=TeacherUnavailabilityResponse)
async def add_teacher_unavailability(
    teacher_id: str,
    unavailability: TeacherUnavailabilityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Add teacher unavailability period."""
    # Check if teacher exists
    teacher = await db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )
    
    # Create unavailability
    db_unavailability = TeacherUnavailability(
        teacher_id=teacher_id,
        **unavailability.model_dump()
    )
    db.add(db_unavailability)
    await db.commit()
    await db.refresh(db_unavailability)
    
    return TeacherUnavailabilityResponse.model_validate(db_unavailability)


@router.delete("/teachers/{teacher_id}/unavailability/{unavailability_id}")
async def remove_teacher_unavailability(
    teacher_id: str,
    unavailability_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Remove teacher unavailability period."""
    result = await db.execute(
        select(TeacherUnavailability).where(
            TeacherUnavailability.id == unavailability_id,
            TeacherUnavailability.teacher_id == teacher_id
        )
    )
    unavailability = result.scalar_one_or_none()
    
    if not unavailability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unavailability not found"
        )
    
    await db.delete(unavailability)
    await db.commit()
    
    return {"message": "Unavailability removed successfully"}