"""Health check route."""

from fastapi import APIRouter

from app.config import APP_VERSION
from app.core.redis import redis_client

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    try:
        redis_client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return {
        "status": "ok" if redis_status == "connected" else "degraded",
        "service": "cart-service",
        "redis": redis_status,
    }
