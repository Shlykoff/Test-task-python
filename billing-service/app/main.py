"""
Billing Service — списание баланса, генерация чеков (Saga через RabbitMQ)
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
from app.core.messaging import consume_order_created
from app.routers import billing, health

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("billing-service")


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    transport = AsyncHTTPTransport()
    _http_client = AsyncClient(transport=transport, timeout=10.0)

    consumer_task = asyncio.create_task(consume_order_created())

    try:
        yield
    finally:
        await _http_client.aclose()
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Billing Service",
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
app.include_router(billing.router)
app.include_router(health.router)
