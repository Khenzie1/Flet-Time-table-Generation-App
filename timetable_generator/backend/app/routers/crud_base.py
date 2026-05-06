"""Base CRUD router factory."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy import inspect as sa_inspect
from typing import Type, TypeVar, List, Optional, Any, Dict
from pydantic import BaseModel

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User

ModelType        = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


def _col_names(model) -> set:
    """Return actual DB column names for a model (no relationships)."""
    return {c.key for c in sa_inspect(model).mapper.column_attrs}


def _to_dict(item, model) -> dict:
    """
    Serialize ORM item to plain dict using only column attributes.
    Converts UUIDs to str so Pydantic str fields validate correctly.
    Avoids touching relationship attrs that trigger lazy-load crashes.
    """
    out = {}
    for col in _col_names(model):
        val = getattr(item, col, None)
        if val is not None and hasattr(val, "hex"):   # UUID -> str
            val = str(val)
        out[col] = val
    return out


async def _school_id(current_user: User, db: AsyncSession) -> Optional[str]:
    """
    Return a usable school_id string.
    Tries current_user.school_id first (may not exist on User model),
    then falls back to the first row in the schools table.
    """
    sid = getattr(current_user, "school_id", None)
    if sid:
        return str(sid)
    try:
        row = (await db.execute(text("SELECT id FROM schools LIMIT 1"))).fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None


def create_crud_router(
    model: Type[ModelType],
    create_schema: Type[CreateSchemaType],
    update_schema: Type[UpdateSchemaType],
    response_schema: Type[BaseModel],
    prefix: str,
    tags: List[str],
    require_school: bool = True,
) -> APIRouter:
    """Create a standard CRUD router for a model."""

    router = APIRouter(prefix=prefix, tags=tags)

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------
    @router.get("", response_model=Dict[str, Any])
    async def list_items(
        skip:  int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(
            require_role(["Admin", "Coordinator", "Viewer"])),
    ):
        sid   = (await _school_id(current_user, db)) if require_school else None
        query = select(model)
        if require_school and sid and hasattr(model, "school_id"):
            query = query.where(model.school_id == sid)

        cq = select(func.count()).select_from(model)
        if require_school and sid and hasattr(model, "school_id"):
            cq = cq.where(model.school_id == sid)

        total  = (await db.execute(cq)).scalar()
        result = await db.execute(query.offset(skip).limit(limit))
        items  = result.scalars().all()

        rows = []
        for item in items:
            try:
                rows.append(
                    response_schema.model_validate(_to_dict(item, model)))
            except Exception:
                pass

        return {"items": rows, "total": total, "skip": skip, "limit": limit}

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    @router.post("", response_model=response_schema,
                 status_code=status.HTTP_201_CREATED)
    async def create_item(
        item_data: create_schema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_role(["Admin", "Coordinator"])),
    ):
        data      = item_data.model_dump()
        valid     = _col_names(model)
        data      = {k: v for k, v in data.items() if k in valid}

        if require_school and hasattr(model, "school_id"):
            # Always resolve school_id server-side — never trust client value
            sid = await _school_id(current_user, db)
            if sid:
                data["school_id"] = sid

        db_item = model(**data)
        db.add(db_item)
        await db.commit()
        await db.refresh(db_item)
        return response_schema.model_validate(_to_dict(db_item, model))

    # ------------------------------------------------------------------
    # GET ONE
    # ------------------------------------------------------------------
    @router.get("/{item_id}", response_model=response_schema)
    async def get_item(
        item_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(
            require_role(["Admin", "Coordinator", "Viewer"])),
    ):
        result = await db.execute(
            select(model).where(model.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} not found")
        return response_schema.model_validate(_to_dict(item, model))

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    @router.put("/{item_id}", response_model=response_schema)
    async def update_item(
        item_id: str,
        item_data: update_schema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_role(["Admin", "Coordinator"])),
    ):
        result = await db.execute(
            select(model).where(model.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} not found")

        valid       = _col_names(model)
        update_data = item_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in valid and field not in ("id", "school_id", "created_at"):
                setattr(item, field, value)

        await db.commit()
        await db.refresh(item)
        return response_schema.model_validate(_to_dict(item, model))

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_item(
        item_id: str,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_role(["Admin", "Coordinator"])),
    ):
        result = await db.execute(
            select(model).where(model.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} not found")
        await db.delete(item)
        await db.commit()
        return None

    return router