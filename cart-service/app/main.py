"""
Cart Service — корзина в Redis, session_id
"""

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import ALLOWED_ORIGINS, APP_VERSION
from app.dependencies import http_client_lifespan
from app.routers import cart, health

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("cart-service")


# --- App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with http_client_lifespan():
        yield


app = FastAPI(
    title="Cart Service",
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
app.include_router(cart.router)
app.include_router(health.router)
