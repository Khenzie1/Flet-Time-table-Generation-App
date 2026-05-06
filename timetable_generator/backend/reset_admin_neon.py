"""
Resets the admin password directly in Neon PostgreSQL.

Run from your backend/ folder (with venv active):

    cd backend
    python reset_admin_neon.py

It reads the same DATABASE_URL that the server uses, so no config needed.
"""
import asyncio
import sys


async def main():
    # ── 1. Load the app's own config so we use the exact same DB URL ─────────
    try:
        from app.config import settings
        db_url = settings.DATABASE_URL
    except Exception as e:
        print(f"Could not load app.config: {e}")
        print("Falling back to manual URL…")
        db_url = input("Paste your DATABASE_URL (postgresql+asyncpg://...): ").strip()

    if not db_url:
        print("❌  No database URL. Exiting.")
        sys.exit(1)

    print(f"Connecting to: {db_url[:60]}…")

    # ── 2. Hash the new password with the same library the app uses ───────────
    try:
        from app.utils.password_handler import get_password_hash
    except ImportError:
        try:
            from passlib.context import CryptContext
            _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            get_password_hash = _ctx.hash
        except ImportError:
            print("❌  passlib not installed. Run: pip install passlib[bcrypt]")
            sys.exit(1)

    NEW_PASSWORD = "admin123"
    new_hash = get_password_hash(NEW_PASSWORD)
    print(f"New hash generated ✓")

    # ── 3. Connect and update ─────────────────────────────────────────────────
    try:
        import sqlalchemy.ext.asyncio as _async_sa
        from sqlalchemy import text

        engine = _async_sa.create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            # Check user exists
            result = await conn.execute(
                text("SELECT id, username, role FROM users WHERE username = :u"),
                {"u": "admin"}
            )
            row = result.fetchone()
            if row is None:
                print("⚠️  No admin user found — creating one…")
                import uuid
                await conn.execute(
                    text("""
                        INSERT INTO users (id, username, email, password_hash, role)
                        VALUES (:id, :u, :e, :h, :r)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "u":  "admin",
                        "e":  "admin@school.edu",
                        "h":  new_hash,
                        "r":  "Admin",
                    }
                )
                print("✅  Admin user created.")
            else:
                await conn.execute(
                    text("UPDATE users SET password_hash = :h WHERE username = :u"),
                    {"h": new_hash, "u": "admin"}
                )
                print(f"✅  Password updated for user: {row.username}  (role: {row.role})")

        await engine.dispose()

    except Exception as e:
        print(f"❌  Database error: {e}")
        sys.exit(1)

    print(f"\n Done! Log in with:  admin  /  {NEW_PASSWORD}")
    print("Restart the server if it is still running.")


asyncio.run(main())