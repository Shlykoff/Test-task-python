"""
Auth Service — JWT: регистрация, логин, refresh, verify
"""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import ALLOWED_ORIGINS, APP_VERSION
from app.dependencies import http_client_lifespan, get_http_client  # noqa: F401
from app.routers import auth, health


# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("auth-service")


# --- App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with http_client_lifespan():
        yield


app = FastAPI(
    title="Auth Service",
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
app.include_router(auth.router)
app.include_router(health.router)
