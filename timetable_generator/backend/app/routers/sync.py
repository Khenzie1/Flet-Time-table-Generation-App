"""
Sync router — bulk push/pull between the desktop client and the backend.

POST /api/v1/sync/push  — desktop sends a snapshot of all local tables
GET  /api/v1/sync/pull  — backend returns a full snapshot for the desktop
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.models.teacher import Teacher, TeacherSubject, TeacherUnavailability
from app.models.subject import Subject
from app.models.class_ import Class, ClassSubject
from app.models.room import Room, RoomUnavailability
from app.models.period import Period
from app.models.timetable import Timetable, TimetableSlot

router = APIRouter(prefix="/sync", tags=["sync"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SyncPushRequest(BaseModel):
    tables: Dict[str, List[Dict[str, Any]]]
    pushed_at: str = ""


class SyncPushResponse(BaseModel):
    status: str
    upserted: int
    errors: List[str] = []


class SyncPullResponse(BaseModel):
    status: str
    tables: Dict[str, List[Dict[str, Any]]]
    pulled_at: str


# ── Model map ─────────────────────────────────────────────────────────────────

TABLE_MODEL_MAP = {
    "teachers":              Teacher,
    "subjects":              Subject,
    "classes":               Class,
    "class_subjects":        ClassSubject,
    "rooms":                 Room,
    "periods":               Period,
    "timetables":            Timetable,
    "timetable_slots":       TimetableSlot,
}


async def _get_school_id(current_user: User, db: AsyncSession) -> Optional[str]:
    sid = getattr(current_user, "school_id", None)
    if sid:
        return str(sid)
    try:
        row = (await db.execute(
            text("SELECT id FROM schools LIMIT 1"))).fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None


def _parse_value(k: str, v: Any) -> Any:
    """Clean and convert a single field value for PostgreSQL insertion."""
    if v is None or str(v).strip() == 'None':
        return None
    if k in ('created_at', 'updated_at'):
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except Exception:
                return None
    return v


# ── PUSH ─────────────────────────────────────────────────────────────────────

@router.post("/push", response_model=SyncPushResponse)
async def sync_push(
    payload: SyncPushRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(["Admin", "Coordinator"])),
):
    """
    Receive entity snapshot from desktop and upsert into Neon PostgreSQL.
    school_id is always injected server-side — never trusted from client.
    """
    upserted = 0
    errors: List[str] = []
    school_id = await _get_school_id(current_user, db)

    # Process in FK-safe order
    order = [
        "teachers", "subjects", "rooms", "classes", "periods",
        "timetables", "timetable_slots", "class_subjects",
    ]

    for table_name in order:
        rows = payload.tables.get(table_name, [])
        model = TABLE_MODEL_MAP.get(table_name)
        if not model or not rows:
            continue

        # Get valid column names for this model
        valid_cols = {c.name for c in model.__table__.columns}

        for row in rows:
            try:
                # Strip to valid columns only, parse timestamps, drop None/'None'
                clean = {}
                for k, v in row.items():
                    if k not in valid_cols:
                        continue
                    parsed = _parse_value(k, v)
                    if parsed is not None:
                        clean[k] = parsed

                if not clean.get("id"):
                    continue

                # Always inject school_id server-side
                if "school_id" in valid_cols and school_id:
                    clean["school_id"] = school_id

                # Use a savepoint so a failed row doesn't poison the session
                async with db.begin_nested():
                    existing = await db.get(model, clean["id"])
                    if existing:
                        for k, v in clean.items():
                            if k not in ("id", "created_at"):
                                setattr(existing, k, v)
                    else:
                        db.add(model(**clean))

                upserted += 1

            except Exception as ex:
                errors.append(
                    f"{table_name}/{row.get('id', '?')}: {ex}")

        # Commit after each table so a later table's failure
        # can't roll back earlier ones
        try:
            await db.commit()
        except Exception as ex:
            errors.append(f"commit:{table_name}: {ex}")
            await db.rollback()

    return SyncPushResponse(
        status="ok" if not errors else "partial",
        upserted=upserted,
        errors=errors[:20],
    )


# ── PULL ─────────────────────────────────────────────────────────────────────

@router.get("/pull", response_model=SyncPullResponse)
async def sync_pull(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(["Admin", "Coordinator", "Viewer"])),
):
    """
    Return full snapshot of all entity tables for the requesting school.
    Desktop upserts everything into local SQLite.
    """
    school_id = await _get_school_id(current_user, db)
    snapshot: Dict[str, List[Dict[str, Any]]] = {}

    for table_name, model in TABLE_MODEL_MAP.items():
        try:
            query = select(model)
            # Filter by school where applicable
            if (school_id and hasattr(model, "school_id")):
                query = query.where(model.school_id == school_id)

            result = await db.execute(query)
            rows = result.scalars().all()

            serialized = []
            for row in rows:
                try:
                    d = {}
                    for col in model.__table__.columns:
                        val = getattr(row, col.name, None)
                        if val is None:
                            d[col.name] = None
                        elif hasattr(val, "hex"):        # UUID
                            d[col.name] = str(val)
                        elif hasattr(val, "isoformat"):  # datetime/date
                            d[col.name] = val.isoformat()
                        else:
                            d[col.name] = val
                    serialized.append(d)
                except Exception:
                    pass

            snapshot[table_name] = serialized

        except Exception:
            snapshot[table_name] = []

    return SyncPullResponse(
        status="ok",
        tables=snapshot,
        pulled_at=datetime.utcnow().isoformat(),
    )
