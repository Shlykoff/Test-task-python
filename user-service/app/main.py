"""
User Service — профиль, баланс, пополнение, CRUD пользователей
"""

import logging
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from app.config import ALLOWED_ORIGINS, APP_VERSION
from app.database import Base, engine, SessionLocal
from app.dependencies import get_db
from app.services.user import seed_data
from app.routers import users, health

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("user-service")


# --- Seed data wrapper ---
def _seed():
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


# --- App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(_seed)
    yield


app = FastAPI(
    title="User Service",
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
app.include_router(users.router)
app.include_router(health.router)
