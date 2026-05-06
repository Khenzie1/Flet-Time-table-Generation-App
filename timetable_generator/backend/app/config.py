"""Configuration management for the application."""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator, AnyHttpUrl
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT")
    DATABASE_URL: Optional[str] = None
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> str:
        """Assemble database connection string for Neon PostgreSQL."""
        if isinstance(v, str):
            # If URL is provided, clean it for asyncpg
            # Remove any query parameters - we'll handle SSL via connect_args
            base_url = v.split('?')[0] if '?' in v else v
            
            # Ensure it uses asyncpg driver
            if "postgresql://" in base_url and "+asyncpg" not in base_url:
                base_url = base_url.replace("postgresql://", "postgresql+asyncpg://")
            
            return base_url
        
        # Build from parts for Neon
        user = values.get('POSTGRES_USER')
        password = values.get('POSTGRES_PASSWORD')
        host = values.get('POSTGRES_HOST')
        port = values.get('POSTGRES_PORT')
        db = values.get('POSTGRES_DB')
        
        # Return URL without SSL params - they'll be handled in connect_args
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))
    
    # Security
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS"))
    CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from string."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        return ["http://localhost", "http://localhost:8550", "http://127.0.0.1:8550"]
    
    # Server
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()