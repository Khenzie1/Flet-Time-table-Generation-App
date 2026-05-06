"""
check_remote.py
---------------
Connects to Neon and prints the exact row counts AND first 5 rows
of each entity table so you can see exactly what data is there.

Run from backend/ with venv active:
    python check_remote.py
"""
import asyncio
import asyncpg
import ssl
import sys

try:
    from app.config import settings
    RAW_URL = settings.DATABASE_URL
except Exception as e:
    print(f"❌ Could not import app.config: {e}")
    sys.exit(1)

def to_asyncpg_dsn(url: str) -> str:
    url = url.split("?")[0]
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url

DSN = to_asyncpg_dsn(RAW_URL)

TABLES = [
    "teachers", "subjects", "classes", "rooms", "periods",
    "timetables", "timetable_slots", "class_subjects",
    "teacher_subjects", "schools", "users",
]

async def main():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    print("\nConnecting to Neon…")
    conn = await asyncpg.connect(DSN, ssl=ssl_ctx)
    print("✅ Connected\n")
    print("=" * 60)
    print(f"{'TABLE':<25} {'ROWS':>6}  SAMPLE DATA")
    print("=" * 60)

    for table in TABLES:
        try:
            count = await conn.fetchval(
                f'SELECT COUNT(*) FROM "{table}"')
            rows = await conn.fetch(
                f'SELECT * FROM "{table}" LIMIT 3')

            if count == 0:
                print(f"\n{table:<25} {count:>6}  ✅ EMPTY")
            else:
                print(f"\n{table:<25} {count:>6}  ⚠️  HAS DATA:")
                for row in rows:
                    # Show name/code/title field if available
                    d = dict(row)
                    preview = (
                        d.get("full_name") or
                        d.get("name") or
                        d.get("code") or
                        d.get("class_name") or
                        d.get("room_code") or
                        d.get("username") or
                        str(d.get("id", ""))[:12]
                    )
                    print(f"  → {preview}")
        except Exception as ex:
            print(f"\n{table:<25}   ERR  {ex}")

    print("\n" + "=" * 60)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())