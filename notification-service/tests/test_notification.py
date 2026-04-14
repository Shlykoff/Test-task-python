"""Тесты notification-service. Используют PostgreSQL test container."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, Notification
from app.dependencies import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@postgres-test:5432/notifications"
test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "notification-service"


# --- Get Notifications ---
async def test_get_notifications_empty(client):
    resp = await client.get("/api/notifications/1")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_notifications(client, db_session):
    db_session.add_all([
        Notification(user_id="1", type="order.created", data={"order_id": 1}),
        Notification(user_id="1", type="order.paid", data={"order_id": 1, "total": 100}),
        Notification(user_id="2", type="order.created", data={"order_id": 2}),
    ])
    db_session.commit()

    resp = await client.get("/api/notifications/1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(n["type"] in ["order.created", "order.paid"] for n in data)


# --- Publish Notification ---
async def test_publish_notification(client):
    resp = await client.post("/api/notifications/publish", json={
        "user_id": "1",
        "type": "order.created",
        "data": {"order_id": 1},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["status"] == "created"


# --- Clear Notifications ---
async def test_clear_notifications(client, db_session):
    db_session.add_all([
        Notification(user_id="1", type="order.created", data={}),
        Notification(user_id="1", type="order.paid", data={}),
    ])
    db_session.commit()

    resp = await client.delete("/api/notifications/1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"

    resp = await client.get("/api/notifications/1")
    assert resp.json() == []


# --- Connection Manager ---
def test_connection_manager():
    from app.core.websocket import manager
    assert len(manager.active_connections) == 0


# --- WebSocket ---
async def test_websocket_requires_token():
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    tc = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with tc.websocket_connect("/ws/notifications") as ws:
            pass

    assert exc_info.value.code == 4001
