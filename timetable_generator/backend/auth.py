"""Authentication – JWT tokens + bcrypt password hashing."""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

import database as db

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY", "changeme-use-a-real-secret-in-production")
ALGORITHM   = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_ctx    = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2     = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Password helpers ──────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


# ── Token helpers ─────────────────────────────────────────────────────────────
def create_token(data: dict, expires_hours: int = TOKEN_EXPIRE_HOURS) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── FastAPI dependency: get current logged-in user ────────────────────────────
def get_current_user(token: str = Depends(oauth2)) -> dict:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    rows = db.query("SELECT * FROM users WHERE username=? AND is_active=1", (username,))
    if not rows:
        raise HTTPException(status_code=401, detail="User not found")
    return rows[0]


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("ADMIN", "COORDINATOR"):
        raise HTTPException(status_code=403, detail="Admin or Coordinator role required")
    return user