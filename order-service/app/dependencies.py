"""Shared dependencies."""

from httpx import AsyncClient

from app.database import SessionLocal


_http_client: AsyncClient | None = None


async def get_http_client() -> AsyncClient:
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
