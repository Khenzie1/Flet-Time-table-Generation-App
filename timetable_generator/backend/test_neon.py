import asyncio
import ssl
import certifi
from sqlalchemy.ext.asyncio import create_async_engine

async def test_neon_connection():
    """Test connection to Neon PostgreSQL."""
    print("Testing connection to Neon PostgreSQL...")
    
    # Database credentials
    user = "him.db_owner"
    password = "npg_4mUWaxDJ5SCw"
    host = "ep-calm-resonance-a6z1f28a-pooler.us-west-2.aws.neon.tech"
    port = "5432"
    database = "him.db"
    
    print(f"Host: {host}")
    print(f"Database: {database}")
    print(f"User: {user}")
    
    # Create SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    # Build connection URL WITHOUT sslmode in the URL string
    # For asyncpg, SSL is configured via connect_args, not in the URL
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    print(f"\nConnecting with URL: {url}")
    print("Using SSL context for secure connection...")
    
    try:
        # Create engine with SSL in connect_args, NOT in URL
        engine = create_async_engine(
            url,
            echo=True,
            connect_args={
                "ssl": ssl_context,  # Pass SSL context directly
                "server_settings": {
                    "application_name": "timetable_generator"
                }
            }
        )
        
        async with engine.connect() as conn:
            # Test basic query
            result = await conn.execute("SELECT 1")
            await conn.commit()
            print("✅ Basic query test passed")
            
            # Get PostgreSQL version
            result = await conn.execute("SELECT version()")
            version = result.scalar()
            print(f"✅ Successfully connected to Neon!")
            print(f"PostgreSQL version: {version}")
            
            # Test creating a table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS connection_test (
                    id SERIAL PRIMARY KEY,
                    test_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.commit()
            print("✅ Table creation test passed")
            
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_neon_connection())