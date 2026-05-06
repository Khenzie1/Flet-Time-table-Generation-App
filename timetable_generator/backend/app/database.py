"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, DeclarativeBase
from sqlalchemy import MetaData
import ssl
import certifi

from app.config import settings

# Create SSL context for Neon
ssl_context = ssl.create_default_context(cafile=certifi.where())

# For asyncpg, we DON'T put sslmode in the URL - we pass it via connect_args
def get_async_database_url():
    """Get properly formatted asyncpg URL for Neon WITHOUT sslmode in URL."""
    url = settings.DATABASE_URL
    
    # Remove any query parameters first
    if '?' in url:
        url = url.split('?')[0]
    
    # Ensure it uses asyncpg driver
    if "postgresql://" in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    
    return url

# Create async engine with Neon-specific settings
async_url = get_async_database_url()
print(f"Connecting to Neon PostgreSQL at: {settings.POSTGRES_HOST}")
print(f"Using URL (without SSL params): {async_url}")

engine = create_async_engine(
    async_url,
    echo=settings.ENVIRONMENT == "development",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before using
    connect_args={
        "ssl": ssl_context,  # Pass SSL context here, NOT in URL
        "server_settings": {
            "application_name": "timetable_generator",
            "timezone": "UTC"
        }
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    
    metadata = MetaData()
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: dict):
        """Update model instance from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def test_connection():
    """Test database connection."""
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
            await conn.commit()
        print("✅ Successfully connected to Neon PostgreSQL!")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Neon: {e}")
        return False