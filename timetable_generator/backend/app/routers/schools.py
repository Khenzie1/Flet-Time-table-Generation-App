"""Schools router — minimal endpoint to allow the desktop client to
   fetch the school_id after login. Single-school app: always returns
   the first (and only) school record."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Any, Dict, List
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User

router = APIRouter(prefix="/schools", tags=["schools"])


class SchoolOut(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    logo_url: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=Dict[str, Any])
async def list_schools(
    limit: int = 10,
    skip: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(["Admin", "Coordinator", "Viewer"])),
):
    """Return all schools (for a single-school app this is always 1 row)."""
    try:
        rows = (await db.execute(
            text("SELECT id, name FROM schools LIMIT :lim OFFSET :sk"),
            {"lim": limit, "sk": skip}
        )).fetchall()
        items = [{"id": str(r[0]), "name": str(r[1])} for r in rows]
        total = len(items)
    except Exception:
        items = []
        total = 0

    return {"items": items, "total": total, "skip": skip, "limit": limit}