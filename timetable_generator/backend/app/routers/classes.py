"""Class routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.class_ import Class, ClassSubject
from app.models.user import User
from app.schemas.class_ import (
    ClassCreate, ClassUpdate, ClassResponse,
    ClassSubjectCreate, ClassSubjectResponse
)
from app.routers.crud_base import create_crud_router

# Create base CRUD router
router = create_crud_router(
    model=Class,
    create_schema=ClassCreate,
    update_schema=ClassUpdate,
    response_schema=ClassResponse,
    prefix="/classes",
    tags=["classes"]
)


@router.post("/classes/{class_id}/subjects", response_model=list[ClassSubjectResponse])
async def assign_class_subjects(
    class_id: str,
    subjects: List[ClassSubjectCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Assign subjects and teachers to a class."""
    # Check if class exists
    class_obj = await db.get(Class, class_id)
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found"
        )
    
    # Remove existing assignments
    await db.execute(
        select(ClassSubject).where(ClassSubject.class_id == class_id)
    )
    
    # Create new assignments
    created_subjects = []
    for subject_data in subjects:
        class_subject = ClassSubject(
            class_id=class_id,
            **subject_data.model_dump()
        )
        db.add(class_subject)
        created_subjects.append(class_subject)
    
    await db.commit()
    
    # Refresh all
    for cs in created_subjects:
        await db.refresh(cs)
    
    return [ClassSubjectResponse.model_validate(cs) for cs in created_subjects]


@router.get("/classes/{class_id}/subjects", response_model=list[ClassSubjectResponse])
async def get_class_subjects(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    """Get subjects assigned to a class."""
    result = await db.execute(
        select(ClassSubject).where(ClassSubject.class_id == class_id)
    )
    subjects = result.scalars().all()
    
    return [ClassSubjectResponse.model_validate(s) for s in subjects]