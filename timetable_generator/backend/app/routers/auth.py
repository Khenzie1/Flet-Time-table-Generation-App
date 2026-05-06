"""Authentication endpoints."""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, TokenRefresh
from app.utils.password_handler import get_password_hash, verify_password
from app.utils.jwt_handler import create_access_token, create_refresh_token, verify_token

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=UserRole(user_data.role)
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create tokens
    token_data = {
        "user_id": str(new_user.id),
        "username": new_user.username,
        "role": new_user.role.value
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(new_user.id),
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role.value,
            "created_at": new_user.created_at.isoformat()
        }
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user."""
    # Find user by username
    result = await db.execute(
        select(User).where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Update last login
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    token_data = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "created_at": user.created_at.isoformat()
        }
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: TokenRefresh):
    """Refresh access token using refresh token."""
    payload = verify_token(refresh_data.refresh_token, token_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Create new tokens
    token_data = {
        "user_id": payload["user_id"],
        "username": payload["username"],
        "role": payload["role"]
    }
    
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    # Return user data (would need to fetch from DB in production)
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user={
            "id": payload["user_id"],
            "username": payload["username"],
            "role": payload["role"],
            "email": "",  # Would need to fetch from DB
            "created_at": datetime.utcnow().isoformat()  # Would need actual created_at
        }
    )


@router.post("/logout")
async def logout():
    """Logout user (client-side token discard)."""
    return {"message": "Successfully logged out"}