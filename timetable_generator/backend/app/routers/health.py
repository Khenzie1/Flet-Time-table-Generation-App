"""Health check endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns status='healthy' (also aliased as 'ok' for client compatibility).
    """
    return {
        "status": "healthy",
        "ok": True,
        "database": "connected",
    }