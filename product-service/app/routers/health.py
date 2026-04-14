"""Health check route."""

from fastapi import APIRouter

from app.config import APP_VERSION

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "product-service", "version": APP_VERSION}
