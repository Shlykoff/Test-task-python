"""Тесты user-service. Используют PostgreSQL из docker-compose."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, get_db


@pytest.fixture
async def client(db_session):
    """HTTP клиент с переопределённой БД."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "user-service"


# --- Create User ---
async def test_create_user(client):
    resp = await client.post("/api/users", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["balance"] == 0.0
    assert "id" in data


async def test_create_user_duplicate(client):
    """Дубликат username/email → 409."""
    await client.post("/api/users", json={
        "username": "dupuser",
        "email": "dup@example.com",
        "password": "password123",
    })
    resp = await client.post("/api/users", json={
        "username": "dupuser",
        "email": "another@example.com",
        "password": "password123",
    })
    assert resp.status_code == 409


async def test_create_user_short_password(client):
    resp = await client.post("/api/users", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "123",
    })
    assert resp.status_code == 422


# --- Get User ---
async def test_get_user(client):
    create_resp = await client.post("/api/users", json={
        "username": "getuser",
        "email": "get@example.com",
        "password": "password123",
    })
    user_id = create_resp.json()["id"]

    resp = await client.get(f"/api/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["username"] == "getuser"


async def test_get_user_not_found(client):
    resp = await client.get("/api/users/9999")
    assert resp.status_code == 404


# --- Verify Password ---
async def test_verify_password(client):
    await client.post("/api/users", json={
        "username": "passuser",
        "email": "pass@example.com",
        "password": "secret123",
    })
    resp = await client.post("/api/users/verify-password", json={
        "username": "passuser",
        "password": "secret123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["username"] == "passuser"


async def test_verify_password_wrong(client):
    await client.post("/api/users", json={
        "username": "wrongpass",
        "email": "wrong@example.com",
        "password": "secret123",
    })
    resp = await client.post("/api/users/verify-password", json={
        "username": "wrongpass",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


# --- Profile ---
async def test_get_profile(client):
    create_resp = await client.post("/api/users", json={
        "username": "profileuser",
        "email": "profile@example.com",
        "password": "password123",
    })
    user_id = create_resp.json()["id"]

    resp = await client.get(f"/api/users/{user_id}/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "profileuser"
    assert "balance" in data


# --- Top Up ---
async def test_topup(client):
    create_resp = await client.post("/api/users", json={
        "username": "topupuser",
        "email": "topup@example.com",
        "password": "password123",
    })
    user_id = create_resp.json()["id"]

    resp = await client.post(f"/api/users/{user_id}/topup", json={"amount": 500.0})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 500.0


async def test_topup_negative(client):
    create_resp = await client.post("/api/users", json={
        "username": "neguser",
        "email": "neg@example.com",
        "password": "password123",
    })
    user_id = create_resp.json()["id"]

    resp = await client.post(f"/api/users/{user_id}/topup", json={"amount": -100})
    assert resp.status_code == 422


# --- Deduct ---
async def test_deduct(client):
    create_resp = await client.post("/api/users", json={
        "username": "deductuser",
        "email": "deduct@example.com",
        "password": "password123",
    })
    user_id = create_resp.json()["id"]

    await client.post(f"/api/users/{user_id}/topup", json={"amount": 1000.0})
    resp = await client.post(f"/api/users/{user_id}/deduct", json={"amount": 300.0})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 700.0


async def test_deduct_insufficient(client):
    create_resp = await client.post("/api/users", json={
        "username": "brokeuser",
        "email": "broke@example.com",
        "password": "password123",
    })
    user_id = create_resp.json()["id"]

    resp = await client.post(f"/api/users/{user_id}/deduct", json={"amount": 500.0})
    assert resp.status_code == 400
