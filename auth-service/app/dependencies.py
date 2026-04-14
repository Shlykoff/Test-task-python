"""Shared dependencies — HTTP client."""

from contextlib import asynccontextmanager

from httpx import AsyncClient, AsyncHTTPTransport


_http_client: AsyncClient | None = None


async def get_http_client() -> AsyncClient:
    """Get the shared HTTP client (must be used within app lifespan)."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


@asynccontextmanager
async def http_client_lifespan():
    """Create and manage the shared HTTP client."""
    global _http_client
    transport = AsyncHTTPTransport()
    _http_client = AsyncClient(transport=transport, timeout=10.0)
    yield
    await _http_client.aclose()
