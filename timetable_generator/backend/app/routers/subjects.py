"""Subject routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.subject import Subject, SubjectCategory
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectUpdate, SubjectResponse
from app.routers.crud_base import create_crud_router

# Create base CRUD router
router = create_crud_router(
    model=Subject,
    create_schema=SubjectCreate,
    update_schema=SubjectUpdate,
    response_schema=SubjectResponse,
    prefix="/subjects",
    tags=["subjects"]
)


@router.get("/subjects/by-category/{category}", response_model=list[SubjectResponse])
async def get_subjects_by_category(
    category: SubjectCategory,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    """Get subjects by category."""
    query = select(Subject).where(
        and_(
            Subject.category == category,
            Subject.school_id == current_user.school_id
        )
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    subjects = result.scalars().all()
    
    return [SubjectResponse.model_validate(s) for s in subjects]