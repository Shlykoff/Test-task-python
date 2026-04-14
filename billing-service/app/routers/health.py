"""Health check route."""

import logging

from fastapi import APIRouter

from app.config import APP_VERSION, RABBITMQ_URL, RABBITMQ_AVAILABLE

logger = logging.getLogger("billing-service")

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    rabbitmq_status = "unknown"
    if RABBITMQ_AVAILABLE:
        try:
            import aio_pika
            conn = await aio_pika.connect_robust(RABBITMQ_URL)
            await conn.close()
            rabbitmq_status = "connected"
        except Exception as e:
            rabbitmq_status = "disconnected"
            logger.warning("RabbitMQ health check failed: %s", e)
    return {
        "status": "ok",
        "service": "billing-service",
        "version": APP_VERSION,
        "rabbitmq": rabbitmq_status,
    }
