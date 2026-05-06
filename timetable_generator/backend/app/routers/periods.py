"""Period routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.period import Period
from app.models.user import User
from app.schemas.period import PeriodCreate, PeriodUpdate, PeriodResponse
from app.routers.crud_base import create_crud_router

# Create base CRUD router
router = create_crud_router(
    model=Period,
    create_schema=PeriodCreate,
    update_schema=PeriodUpdate,
    response_schema=PeriodResponse,
    prefix="/periods",
    tags=["periods"]
)


@router.get("/periods/by-day/{day}", response_model=list[PeriodResponse])
async def get_periods_by_day(
    day: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    """Get periods for a specific day."""
    query = select(Period).where(
        and_(
            Period.day_of_week == day,
            Period.school_id == current_user.school_id
        )
    ).order_by(Period.period_number)
    
    result = await db.execute(query)
    periods = result.scalars().all()
    
    return [PeriodResponse.model_validate(p) for p in periods]