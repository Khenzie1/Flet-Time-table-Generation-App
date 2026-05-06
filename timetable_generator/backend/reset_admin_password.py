"""
Run this once from inside your backend/ folder to fix the admin password.

    cd backend
    python reset_admin_password.py

"""
import sqlite3
from pathlib import Path

try:
    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_ctx.hash("admin123")
    print(f"Generated hash: {password_hash}")
except ImportError:
    print("passlib not found, installing...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "passlib[bcrypt]"])
    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_ctx.hash("admin123")
    print(f"Generated hash: {password_hash}")

# Find the database
db_path = Path("timetable_server.db")
if not db_path.exists():
    print(f"Database not found at {db_path}. Run the server first to create it, then run this script.")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.execute("PRAGMA foreign_keys=ON")

# Check if admin exists
existing = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()

if existing:
    conn.execute(
        "UPDATE users SET password_hash=? WHERE username='admin'",
        (password_hash,)
    )
    print("✅ Admin password updated to: admin123")
else:
    import uuid
    conn.execute(
        "INSERT INTO users (id, username, email, password_hash, role) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), "admin", "admin@school.edu", password_hash, "ADMIN")
    )
    print("✅ Admin user created with password: admin123")

conn.commit()
conn.close()
print("\nDone. Restart the server and try logging in with admin / admin123")