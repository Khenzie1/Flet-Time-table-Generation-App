"""Room routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.room import Room, RoomUnavailability, RoomType
from app.models.user import User
from app.schemas.room import (
    RoomCreate, RoomUpdate, RoomResponse,
    RoomUnavailabilityCreate, RoomUnavailabilityResponse
)
from app.routers.crud_base import create_crud_router

# Create base CRUD router
router = create_crud_router(
    model=Room,
    create_schema=RoomCreate,
    update_schema=RoomUpdate,
    response_schema=RoomResponse,
    prefix="/rooms",
    tags=["rooms"]
)


@router.get("/rooms/by-type/{room_type}", response_model=list[RoomResponse])
async def get_rooms_by_type(
    room_type: RoomType,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator", "Viewer"]))
):
    """Get rooms by type."""
    query = select(Room).where(
        and_(
            Room.room_type == room_type,
            Room.school_id == current_user.school_id
        )
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    rooms = result.scalars().all()
    
    return [RoomResponse.model_validate(r) for r in rooms]


@router.post("/rooms/{room_id}/unavailability", response_model=RoomUnavailabilityResponse)
async def add_room_unavailability(
    room_id: str,
    unavailability: RoomUnavailabilityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Add room unavailability period."""
    # Check if room exists
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    
    # Create unavailability
    db_unavailability = RoomUnavailability(
        room_id=room_id,
        **unavailability.model_dump()
    )
    db.add(db_unavailability)
    await db.commit()
    await db.refresh(db_unavailability)
    
    return RoomUnavailabilityResponse.model_validate(db_unavailability)


@router.delete("/rooms/{room_id}/unavailability/{unavailability_id}")
async def remove_room_unavailability(
    room_id: str,
    unavailability_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Coordinator"]))
):
    """Remove room unavailability period."""
    result = await db.execute(
        select(RoomUnavailability).where(
            RoomUnavailability.id == unavailability_id,
            RoomUnavailability.room_id == room_id
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