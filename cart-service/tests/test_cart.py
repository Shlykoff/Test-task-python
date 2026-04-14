"""Тесты cart-service (с мокнутым Redis и product-service)."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport, Response
from app.main import app
from app.core.redis import redis_client
from app.dependencies import _http_client

# Mock Redis
class MockRedis:
    def __init__(self):
        self.data = {}
        self.ttl = {}

    def hgetall(self, key):
        return self.data.get(key, {})

    def hset(self, key, mapping=None, **kwargs):
        if key not in self.data:
            self.data[key] = {}
        if mapping:
            self.data[key].update(mapping)

    def expire(self, key, seconds):
        pass

    def delete(self, key):
        self.data.pop(key, None)

    def ping(self):
        return True

    def pipeline(self):
        return MockPipeline(self)


class MockPipeline:
    def __init__(self, redis_obj):
        self.redis = redis_obj
        self.ops = []

    def delete(self, key):
        self.ops.append(("delete", key))
        return self

    def hset(self, key, mapping=None, **kwargs):
        self.ops.append(("hset", key, mapping))
        return self

    def expire(self, key, seconds):
        self.ops.append(("expire", key, seconds))
        return self

    def execute(self):
        for op in self.ops:
            if op[0] == "delete":
                self.redis.delete(op[1])
            elif op[0] == "hset":
                self.redis.hset(op[1], mapping=op[2])
            elif op[0] == "expire":
                self.redis.expire(op[1], op[2])
        self.ops = []
        return [True] * len(self.ops)


@pytest.fixture(autouse=True)
def mock_redis():
    mock = MockRedis()
    with patch("app.core.redis.redis_client", mock):
        yield mock


@pytest.fixture(autouse=True)
def mock_http_client():
    """Mock the shared _http_client for product-service calls."""
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 1, "name": "Test Product", "user_price": 100.0,
        "cost_price": 83.33, "quantity": 10,
    }

    mock_client = AsyncMock(spec=AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.delete = AsyncMock(return_value=mock_resp)

    with patch("app.dependencies._http_client", mock_client):
        yield mock_client


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "cart-service"


# --- Get Cart (empty) ---
async def test_get_cart_empty(client):
    resp = await client.get("/api/cart", headers={"X-Session-Id": "test-session"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0.0
    assert data["session_id"] == "test-session"


# --- Add Item ---
async def test_add_item(client, mock_redis, mock_http_client):
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": 1, "quantity": 2},
        headers={"X-Session-Id": "test-session"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["product_id"] == 1
    assert data["quantity"] == 2


# --- Update Item ---
async def test_update_item(client, mock_redis):
    mock_redis.hset("cart:test-session", mapping={"1": "3"})

    resp = await client.patch(
        "/api/cart/items/1",
        json={"quantity": 5},
        headers={"X-Session-Id": "test-session"},
    )
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 5


async def test_update_item_not_found(client):
    resp = await client.patch(
        "/api/cart/items/99",
        json={"quantity": 1},
        headers={"X-Session-Id": "test-session"},
    )
    assert resp.status_code == 404


# --- Remove Item ---
async def test_remove_item(client, mock_redis):
    mock_redis.hset("cart:test-session", mapping={"1": "3", "2": "1"})

    resp = await client.delete(
        "/api/cart/items/1",
        headers={"X-Session-Id": "test-session"},
    )
    assert resp.status_code == 200
    assert resp.json()["product_id"] == 1


# --- Clear Cart ---
async def test_clear_cart(client, mock_redis):
    mock_redis.hset("cart:test-session", mapping={"1": "3"})

    resp = await client.delete(
        "/api/cart",
        headers={"X-Session-Id": "test-session"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"
