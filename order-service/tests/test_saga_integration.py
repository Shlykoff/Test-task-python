"""Интеграционные тесты Saga: order → billing → order. Используют PostgreSQL test container."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport, Response
from decimal import Decimal

from app.main import app
from app.database import Base, Order, OrderItem, SessionLocal
from app.dependencies import get_db, _http_client
from app.routers.orders import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@postgres-test:5432/orders"
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

    async def override_get_user():
        return {"user_id": 1, "username": "testuser"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _mock_resp(status, body):
    m = MagicMock(spec=Response)
    m.status_code = status
    m.json.return_value = body
    return m


@pytest.fixture
def mock_services():
    cart = _mock_resp(200, {
        "session_id": "test-session",
        "items": [
            {"product_id": 1, "product_name": "Test Product",
             "quantity": 2, "user_price": 100.0},
        ],
        "total": 200.0,
    })
    product = _mock_resp(200, {
        "id": 1, "name": "Test Product", "user_price": 100.0,
        "cost_price": 83.33, "quantity": 10,
    })
    reserve = _mock_resp(200, {"success": True, "product_id": 1, "remaining_quantity": 8})

    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=lambda url, **kw: cart if "cart" in str(url) else product)
    mock.post = AsyncMock(return_value=reserve)
    mock.delete = AsyncMock(return_value=_mock_resp(200, {}))

    with patch("app.dependencies._http_client", mock):
        yield mock


# ─── Create Order (Saga) ───

async def test_create_order_returns_202(client, mock_services):
    """POST /orders/create → 202 Accepted, status=pending."""
    resp = await client.post("/api/orders/create", json={"session_id": "test-session"})
    assert resp.status_code == 202
    data = resp.json()
    assert data["order_id"] is not None
    assert data["status"] == "pending"


async def test_create_order_idempotent(client, mock_services):
    """Одинаковый X-Idempotency-Key → тот же заказ."""
    r1 = await client.post(
        "/api/orders/create",
        json={"session_id": "test-session"},
        headers={"X-Idempotency-Key": "idem-1"},
    )
    assert r1.status_code == 202
    oid1 = r1.json()["order_id"]

    r2 = await client.post(
        "/api/orders/create",
        json={"session_id": "test-session"},
        headers={"X-Idempotency-Key": "idem-1"},
    )
    assert r2.status_code == 202
    assert r2.json()["order_id"] == oid1


# ─── Order status transitions ───

def test_order_pending_to_paid(db_session):
    o = Order(user_id=1, total=Decimal("100.00"), status="pending", session_id="s1")
    db_session.add(o)
    db_session.commit()
    assert o.status == "pending"
    o.status = "paid"
    db_session.commit()
    assert o.status == "paid"


def test_order_pending_to_cancelled(db_session):
    o = Order(user_id=1, total=Decimal("200.00"), status="pending", session_id="s2")
    db_session.add(o)
    db_session.commit()
    o.status = "cancelled"
    db_session.commit()
    assert o.status == "cancelled"
