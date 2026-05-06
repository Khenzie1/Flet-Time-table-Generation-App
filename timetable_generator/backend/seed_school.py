"""
Creates a School record in Neon PostgreSQL and links the admin user to it.
This is required before any teacher/subject/class/room records can be created,
because they all have a NOT NULL foreign key to the schools table.

Run from your backend/ folder (with venv active):

    cd backend
    python seed_school.py
"""
import asyncio
import sys
import uuid


async def main():
    # ── Load app config for DB URL ────────────────────────────────────────────
    try:
        from app.config import settings
        db_url = settings.DATABASE_URL
    except Exception as e:
        print(f"Could not load app.config: {e}")
        db_url = input("Paste your DATABASE_URL (postgresql+asyncpg://...): ").strip()

    if not db_url:
        print("❌  No database URL. Exiting.")
        sys.exit(1)

    print(f"Connecting to: {db_url[:60]}…")

    import sqlalchemy.ext.asyncio as _sa
    from sqlalchemy import text

    engine = _sa.create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:

        # ── 1. Check if a school already exists ───────────────────────────────
        result = await conn.execute(text("SELECT id, name FROM schools LIMIT 1"))
        existing = result.fetchone()

        if existing:
            school_id = str(existing.id)
            print(f"✓ School already exists: '{existing.name}'  id={school_id}")
        else:
            # ── 2. Create the school ──────────────────────────────────────────
            school_id = str(uuid.uuid4())
            await conn.execute(text("""
                INSERT INTO schools (id, name, address, created_at, updated_at)
                VALUES (:id, :name, :address, NOW(), NOW())
            """), {
                "id":      school_id,
                "name":    "Migrant Model Secondary School",
                "address": "Lagos, Nigeria",
            })
            print(f"✅  School created: 'Migrant Model Secondary School'  id={school_id}")

        # ── 3. Link the admin user to this school ─────────────────────────────
        # Check if users table has a school_id column
        col_check = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'school_id'
        """))
        has_school_col = col_check.fetchone() is not None

        if has_school_col:
            # Update all users that don't have a school_id yet
            update = await conn.execute(text("""
                UPDATE users SET school_id = :sid
                WHERE school_id IS NULL OR school_id::text = ''
            """), {"sid": school_id})
            print(f"✅  Linked {update.rowcount} user(s) to the school.")
        else:
            print("⚠️  users table has no school_id column — skipping user link.")
            print("    This is OK if your User model doesn't have school_id.")

        # ── 4. Show result ────────────────────────────────────────────────────
        users = await conn.execute(text(
            "SELECT username, role FROM users ORDER BY role"
        ))
        print("\nUsers in DB:")
        for row in users:
            print(f"  {row.username:<20} role={row.role}")

    await engine.dispose()
    print(f"\n✅  Done. school_id to use: {school_id}")
    print("   Restart the backend, then try Sync Now again.")


asyncio.run(main())