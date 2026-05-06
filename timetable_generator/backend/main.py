"""
Smart Timetable Generator – FastAPI Backend
==========================================
Endpoints:
  POST   /api/v1/auth/login
  POST   /api/v1/auth/change-password

  GET    /api/v1/{entity}          list   (teachers/classes/subjects/rooms/timetables)
  POST   /api/v1/{entity}          create
  PUT    /api/v1/{entity}/{id}     update
  DELETE /api/v1/{entity}/{id}     delete

  POST   /api/v1/sync/push         receive full local snapshot → merge into server
  GET    /api/v1/sync/pull         return full server snapshot for local DB

  POST   /api/v1/reports/summary   aggregated stats

  GET    /api/v1/health            connectivity check
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Any, Optional
import uuid, time

import database as db
import auth

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Smart Timetable Generator API",
    version="1.0.0",
    description="Backend for the school timetable desktop application",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    db.init_db()
    print("🚀 Timetable backend started")


# ── Pydantic models ───────────────────────────────────────────────────────────
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class SyncPush(BaseModel):
    tables: dict   # { "teachers": [...], "classes": [...], ... }
    pushed_at: Optional[str] = None

class ReportRequest(BaseModel):
    timetable_id: Optional[str] = None
    term: Optional[str] = None
    academic_year: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "SmartTimetableGenerator"}


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    rows = db.query("SELECT * FROM users WHERE username=? AND is_active=1",
                    (form.username,))
    if not rows:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = rows[0]
    if not auth.verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth.create_token({"sub": user["username"], "role": user["role"]})
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"access_token": token, "token_type": "bearer", "user": safe_user}


@app.post("/api/v1/auth/change-password")
def change_password(body: ChangePassword,
                    current_user: dict = Depends(auth.get_current_user)):
    if not auth.verify_password(body.old_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    new_hash = auth.hash_password(body.new_password)
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (new_hash, current_user["id"]))
    return {"message": "Password changed successfully"}


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC CRUD  (teachers, classes, subjects, rooms, timetables, users)
# ══════════════════════════════════════════════════════════════════════════════
ALLOWED_TABLES = {
    "teachers", "classes", "subjects", "rooms",
    "timetables", "timetable_slots", "class_subjects",
    "teacher_subjects", "teacher_unavailability",
    "rooms_unavailability", "users",
}


def _check_table(table: str):
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"Unknown entity: {table}")


@app.get("/api/v1/{table}")
def list_entities(table: str,
                  _: dict = Depends(auth.get_current_user)):
    _check_table(table)
    rows = db.query(f"SELECT * FROM {table} ORDER BY rowid DESC")
    return {"items": rows, "total": len(rows)}


@app.get("/api/v1/{table}/{item_id}")
def get_entity(table: str, item_id: str,
               _: dict = Depends(auth.get_current_user)):
    _check_table(table)
    rows = db.query(f"SELECT * FROM {table} WHERE id=?", (item_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    return rows[0]


@app.post("/api/v1/{table}", status_code=201)
def create_entity(table: str, body: dict,
                  _: dict = Depends(auth.require_admin)):
    _check_table(table)
    if "id" not in body or not body["id"]:
        body["id"] = db.new_id()
    cols   = ", ".join(body.keys())
    placeholders = ", ".join("?" for _ in body)
    db.execute(
        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
        tuple(body.values()),
    )
    return {"id": body["id"], "message": f"{table[:-1].title()} created"}


@app.put("/api/v1/{table}/{item_id}")
def update_entity(table: str, item_id: str, body: dict,
                  _: dict = Depends(auth.require_admin)):
    _check_table(table)
    body.pop("id", None)
    if not body:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k}=?" for k in body)
    db.execute(
        f"UPDATE {table} SET {set_clause} WHERE id=?",
        (*body.values(), item_id),
    )
    return {"id": item_id, "message": "Updated"}


@app.delete("/api/v1/{table}/{item_id}")
def delete_entity(table: str, item_id: str,
                  _: dict = Depends(auth.require_admin)):
    _check_table(table)
    db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# TIMETABLE  (enriched slot query)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/v1/timetables/{timetable_id}/slots")
def get_timetable_slots(timetable_id: str,
                        _: dict = Depends(auth.get_current_user)):
    slots = db.query("""
        SELECT ts.*,
               s.code  AS subject_code,
               s.name  AS subject_name,
               s.category,
               t.full_name   AS teacher_name,
               t.teacher_code,
               c.class_name,
               r.room_code,
               r.room_name
        FROM timetable_slots ts
        JOIN subjects s  ON s.id  = ts.subject_id
        JOIN teachers t  ON t.id  = ts.teacher_id
        JOIN classes  c  ON c.id  = ts.class_id
        LEFT JOIN rooms r ON r.id = ts.room_id
        WHERE ts.timetable_id = ?
        ORDER BY ts.day_of_week, ts.period_number
    """, (timetable_id,))
    return {"timetable_id": timetable_id, "slots": slots}


# ══════════════════════════════════════════════════════════════════════════════
# SYNC  – push local → server / pull server → local
# ══════════════════════════════════════════════════════════════════════════════
SYNC_TABLES_ORDER = [
    "teachers", "subjects", "rooms", "classes",
    "class_subjects", "teacher_subjects",
    "teacher_unavailability", "rooms_unavailability",
    "timetables", "timetable_slots",
]

@app.post("/api/v1/sync/push")
def sync_push(body: SyncPush,
              _: dict = Depends(auth.require_admin)):
    """
    Desktop app calls this after any significant change.
    Each table's rows are upserted (INSERT OR REPLACE) into the server DB.
    """
    total = 0
    errors = []
    for table in SYNC_TABLES_ORDER:
        rows = body.tables.get(table, [])
        for row in rows:
            try:
                if "id" not in row:
                    continue
                cols  = ", ".join(row.keys())
                ph    = ", ".join("?" for _ in row)
                db.execute(
                    f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({ph})",
                    tuple(row.values()),
                )
                total += 1
            except Exception as ex:
                errors.append(f"{table}/{row.get('id', '?')}: {ex}")

    return {
        "status": "ok",
        "records": total,
        "errors": errors,
        "pushed_at": body.pushed_at,
    }


@app.get("/api/v1/sync/pull")
def sync_pull(_: dict = Depends(auth.get_current_user)):
    """
    Desktop app calls this to get the full server state for seeding local DB.
    """
    snapshot = {}
    for table in SYNC_TABLES_ORDER:
        try:
            snapshot[table] = db.query(f"SELECT * FROM {table}")
        except Exception:
            snapshot[table] = []
    return {"status": "ok", "tables": snapshot}


# ══════════════════════════════════════════════════════════════════════════════
# REPORTS  – aggregated stats
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/v1/reports/summary")
def reports_summary(body: ReportRequest,
                    _: dict = Depends(auth.get_current_user)):
    teachers = db.query("SELECT COUNT(*) AS cnt FROM teachers WHERE is_active=1")[0]["cnt"]
    classes  = db.query("SELECT COUNT(*) AS cnt FROM classes")[0]["cnt"]
    subjects = db.query("SELECT COUNT(*) AS cnt FROM subjects")[0]["cnt"]
    rooms    = db.query("SELECT COUNT(*) AS cnt FROM rooms WHERE is_available=1")[0]["cnt"]

    slot_count = 0
    conflicts  = []
    if body.timetable_id:
        slot_count = db.query(
            "SELECT COUNT(*) AS cnt FROM timetable_slots WHERE timetable_id=?",
            (body.timetable_id,)
        )[0]["cnt"]

        # Teacher double-booking
        conflicts_raw = db.query("""
            SELECT teacher_id, day_of_week, period_number, COUNT(*) AS cnt
            FROM timetable_slots
            WHERE timetable_id=?
            GROUP BY teacher_id, day_of_week, period_number
            HAVING cnt > 1
        """, (body.timetable_id,))
        conflicts = conflicts_raw

    return {
        "teachers": teachers,
        "classes":  classes,
        "subjects": subjects,
        "rooms":    rooms,
        "slots_scheduled": slot_count,
        "conflicts": conflicts,
    }


# ══════════════════════════════════════════════════════════════════════════════
# USERS MANAGEMENT (admin only)
# ══════════════════════════════════════════════════════════════════════════════
class CreateUser(BaseModel):
    username: str
    email: str
    password: str
    role: str = "VIEWER"

class UpdateUser(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[int] = None


@app.post("/api/v1/users", status_code=201)
def create_user(body: CreateUser,
                _: dict = Depends(auth.require_admin)):
    existing = db.query("SELECT id FROM users WHERE username=?", (body.username,))
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    uid = db.new_id()
    db.execute(
        "INSERT INTO users (id, username, email, password_hash, role) VALUES (?,?,?,?,?)",
        (uid, body.username, body.email, auth.hash_password(body.password), body.role),
    )
    return {"id": uid, "message": "User created"}


@app.put("/api/v1/users/{user_id}")
def update_user(user_id: str, body: UpdateUser,
                _: dict = Depends(auth.require_admin)):
    updates = {}
    if body.email:     updates["email"]    = body.email
    if body.role:      updates["role"]     = body.role
    if body.password:  updates["password_hash"] = auth.hash_password(body.password)
    if body.is_active is not None: updates["is_active"] = body.is_active
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    set_cl = ", ".join(f"{k}=?" for k in updates)
    db.execute(f"UPDATE users SET {set_cl} WHERE id=?", (*updates.values(), user_id))
    return {"message": "User updated"}