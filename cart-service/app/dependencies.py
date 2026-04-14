"""Shared dependencies — HTTP client, session helpers."""

import uuid
from contextlib import asynccontextmanager

from fastapi import Request, Response
from httpx import AsyncClient, AsyncHTTPTransport

from app.config import CART_TTL_SECONDS

_http_client: AsyncClient | None = None


def get_session_id(request: Request) -> str:
    session_id = request.headers.get("X-Session-Id") or request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


def set_session_cookie(response: Response, session_id: str):
    response.set_cookie("session_id", session_id, max_age=CART_TTL_SECONDS, httponly=True)


async def get_http_client() -> AsyncClient:
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


@asynccontextmanager
async def http_client_lifespan():
    global _http_client
    transport = AsyncHTTPTransport()
    _http_client = AsyncClient(transport=transport, timeout=10.0)
    yield
    await _http_client.aclose()
