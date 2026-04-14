"""
Order Service — создание заказов (Saga через RabbitMQ)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, AsyncHTTPTransport
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import ALLOWED_ORIGINS, APP_VERSION
from app.dependencies import get_db, get_http_client, _http_client
from app.core.messaging import (
    consume_payment_completed,
    consume_payment_failed,
    saga_timeout_checker,
)
from app.routers import orders, health

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("order-service")


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    transport = AsyncHTTPTransport()
    _http_client = AsyncClient(transport=transport, timeout=10.0)

    consumer_tasks = [
        asyncio.create_task(consume_payment_completed()),
        asyncio.create_task(consume_payment_failed()),
        asyncio.create_task(saga_timeout_checker()),
    ]

    try:
        yield
    finally:
        await _http_client.aclose()
        for task in consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Order Service",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(orders.router)
app.include_router(health.router)
