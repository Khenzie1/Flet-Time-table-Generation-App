"""SQLite database layer for the backend — same schema as the desktop app."""
import sqlite3
import uuid
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "timetable_server.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'VIEWER',
    school_id     TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schools (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    address    TEXT,
    logo_url   TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teachers (
    id               TEXT PRIMARY KEY,
    teacher_code     TEXT NOT NULL UNIQUE,
    full_name        TEXT NOT NULL,
    email            TEXT,
    phone            TEXT,
    max_daily_periods INTEGER DEFAULT 6,
    is_active        INTEGER DEFAULT 1,
    subject_codes    TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id               TEXT PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    category         TEXT DEFAULT 'Core',
    periods_per_week INTEGER DEFAULT 3,
    requires_lab     INTEGER DEFAULT 0,
    duration_minutes INTEGER DEFAULT 40,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classes (
    id              TEXT PRIMARY KEY,
    class_name      TEXT NOT NULL UNIQUE,
    level           TEXT,
    student_count   INTEGER DEFAULT 40,
    default_room_id TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rooms (
    id           TEXT PRIMARY KEY,
    room_code    TEXT NOT NULL UNIQUE,
    room_name    TEXT NOT NULL,
    room_type    TEXT DEFAULT 'Regular',
    capacity     INTEGER DEFAULT 40,
    is_available INTEGER DEFAULT 1,
    subject_code TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_subjects (
    id         TEXT PRIMARY KEY,
    class_id   TEXT NOT NULL REFERENCES classes(id),
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    teacher_id TEXT NOT NULL REFERENCES teachers(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teacher_subjects (
    id         TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL REFERENCES teachers(id),
    subject_id TEXT NOT NULL REFERENCES subjects(id)
);

CREATE TABLE IF NOT EXISTS teacher_unavailability (
    id         TEXT PRIMARY KEY,
    teacher_id TEXT NOT NULL REFERENCES teachers(id),
    day_of_week TEXT NOT NULL,
    period_number INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms_unavailability (
    id         TEXT PRIMARY KEY,
    room_id    TEXT NOT NULL REFERENCES rooms(id),
    day_of_week TEXT NOT NULL,
    period_number INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS timetables (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    type          TEXT DEFAULT 'Class Timetable',
    term          TEXT,
    academic_year TEXT,
    status        TEXT DEFAULT 'Draft',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS timetable_slots (
    id            TEXT PRIMARY KEY,
    timetable_id  TEXT NOT NULL REFERENCES timetables(id),
    class_id      TEXT NOT NULL REFERENCES classes(id),
    subject_id    TEXT NOT NULL REFERENCES subjects(id),
    teacher_id    TEXT NOT NULL REFERENCES teachers(id),
    room_id       TEXT REFERENCES rooms(id),
    day_of_week   TEXT NOT NULL,
    period_number INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Admin user seeded by init_db() in Python (not here)
-- so the password hash is always generated correctly at runtime.
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executescript(SCHEMA)

    # Seed default admin with a real bcrypt hash
    existing = query("SELECT id FROM users WHERE username='admin'")
    if not existing:
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed  = pwd_ctx.hash("admin123")
        execute(
            "INSERT OR IGNORE INTO users (id, username, email, password_hash, role) "
            "VALUES (?,?,?,?,?)",
            (new_id(), "admin", "admin@school.edu", hashed, "ADMIN"),
        )
        print("✅ Default admin user seeded (admin / admin123)")

    print(f"✅ Server database initialised at {DB_PATH}")


def query(sql: str, params: tuple = ()):
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(sql: str, params: tuple = ()):
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


def new_id() -> str:
    return str(uuid.uuid4())