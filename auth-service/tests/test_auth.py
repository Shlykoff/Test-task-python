"""Тесты auth-service."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token, create_refresh_token, decode_token


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "auth-service"


# --- Register ---
async def test_register_success(monkeypatch, client):
    """Регистрация должна вызвать user-service и вернуть токены."""

    class MockResponse:
        status_code = 201

        def json(self):
            return {"id": 1, "username": "testuser", "email": "test@example.com"}

    async def mock_post(*args, **kwargs):
        return MockResponse()

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        post = mock_post

    monkeypatch.setattr("app.dependencies._http_client", MockClient())

    resp = await client.post("/api/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


async def test_register_duplicate(client, monkeypatch):
    """Дубликат должен вернуть 409."""

    class MockResponse:
        status_code = 409

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("app.dependencies._http_client", MockClient())

    resp = await client.post("/api/register", json={
        "username": "existing",
        "email": "existing@example.com",
        "password": "password123",
    })
    assert resp.status_code == 409


# --- Login ---
async def test_login_success(client, monkeypatch):
    """Логин должен проверить пароль через user-service и вернуть токены."""

    class MockResponse:
        status_code = 200

        def json(self):
            return {"user_id": 1, "username": "testuser"}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("app.dependencies._http_client", MockClient())

    resp = await client.post("/api/token", json={
        "username": "testuser",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


async def test_login_invalid_credentials(client, monkeypatch):
    """Неверные данные должны вернуть 401."""

    class MockResponse:
        status_code = 401

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("app.dependencies._http_client", MockClient())

    resp = await client.post("/api/token", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


# --- Refresh ---
async def test_refresh_token(client, monkeypatch):
    """Валидный refresh-токен должен вернуть новый access-токен."""

    class MockResponse:
        status_code = 200

        def json(self):
            return {"id": 1, "username": "testuser"}

    class MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("app.dependencies._http_client", MockClient())

    refresh = create_refresh_token({"sub": "1"})
    resp = await client.post("/api/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_invalid_token(client):
    """Невалидный refresh-токен должен вернуть 401."""
    resp = await client.post("/api/refresh", json={"refresh_token": "invalid.token.here"})
    assert resp.status_code == 401


# --- Verify Token ---
async def test_verify_token_valid(client):
    """Валидный access-токен должен вернуть valid=True."""
    token = create_access_token({"sub": "1", "username": "testuser"})
    resp = await client.post("/api/verify", json={"token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["user_id"] == "1"


async def test_verify_token_invalid(client):
    """Невалидный токен должен вернуть valid=False."""
    resp = await client.post("/api/verify", json={"token": "invalid.token.here"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False


# --- JWT Helpers ---
def test_create_and_decode_token():
    token = create_access_token({"sub": "42", "username": "test"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["username"] == "test"


def test_decode_wrong_type():
    refresh = create_refresh_token({"sub": "42"})
    payload = decode_token(refresh, expected_type="access")
    assert payload is None
