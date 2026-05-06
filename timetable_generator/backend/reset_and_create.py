"""Simple script to reset and create all tables."""
import asyncio
import ssl
import certifi
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings
from app.database import Base

# Import ALL models to ensure they're registered
from app.models.user import User
from app.models.school import School
from app.models.teacher import Teacher, TeacherSubject, TeacherUnavailability
from app.models.subject import Subject
from app.models.class_ import Class, ClassSubject
from app.models.room import Room, RoomUnavailability
from app.models.period import Period
from app.models.timetable import Timetable, TimetableSlot
from app.models.sync import SyncQueue, AuditLog

async def reset_and_create():
    """Reset database and create all tables."""
    print("=" * 60)
    print("CONNECTING TO NEON POSTGRESQL")
    print("=" * 60)
    print(f"Host: {settings.POSTGRES_HOST}")
    print(f"Database: {settings.POSTGRES_DB}")
    print(f"User: {settings.POSTGRES_USER}")
    print("=" * 60)
    
    # Create SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    # Build clean URL without any parameters
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    print(f"\nConnecting...")
    
    # Create engine with SSL
    engine = create_async_engine(
        url,
        echo=True,
        connect_args={
            "ssl": ssl_context,
            "server_settings": {"application_name": "timetable_creator"}
        }
    )
    
    try:
        # Test connection first - FIXED: Use text() object
        print("\n🔍 Testing connection...")
        async with engine.connect() as conn:
            # Use text() for raw SQL strings
            result = await conn.execute(text("SELECT 1"))
            await conn.commit()
            print("✅ Connection successful!")
            
            # Check current tables - FIXED: Use text()
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            existing = [row[0] for row in result.fetchall()]
            
            if existing:
                print(f"\n📊 Found {len(existing)} existing tables:")
                for table in existing:
                    print(f"   - {table}")
                
                print("\n🗑️  Dropping all tables...")
                # Drop schema - FIXED: Use text() and execute
                await conn.execute(text("DROP SCHEMA public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
                await conn.commit()
                print("✅ All tables dropped!")
        
        # Create all tables
        print("\n🏗️  Creating all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ All tables created successfully!")
        
        # Verify tables were created
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            created = [row[0] for row in result.fetchall()]
            
            print(f"\n📋 Tables created ({len(created)}):")
            for table in created:
                print(f"   ✅ {table}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()
        print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(reset_and_create())