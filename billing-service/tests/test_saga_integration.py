"""Интеграционные тесты billing-service Saga. Используют PostgreSQL test container."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport, Response
from decimal import Decimal

from app.main import app
from app.database import Base, Receipt, SessionLocal
from app.dependencies import get_db, _http_client
from app.services.billing import process_payment_core
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@postgres-test:5432/billing"
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


@pytest.fixture
def mock_http_client():
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 1, "balance": 500.0}

    mock = AsyncMock()
    mock.get = AsyncMock(return_value=mock_resp)
    mock.post = AsyncMock(return_value=mock_resp)

    with patch("app.dependencies._http_client", mock):
        yield mock


# --- Test: Successful payment ---
async def test_process_payment_success(client, mock_http_client):
    """Оплата проходит — чек создан."""
    resp = await client.post(
        "/api/payments",
        json={"order_id": 1, "user_id": 1, "amount": 100.0, "items": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["receipt_id"] is not None


# --- Test: Payment failed — insufficient balance ---
async def test_process_payment_insufficient_balance(client, mock_http_client):
    """Недостаточно баланса — payment.failed."""
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 1, "balance": 10.0}
    mock_http_client.get = AsyncMock(return_value=mock_resp)

    resp = await client.post(
        "/api/payments",
        json={"order_id": 1, "user_id": 1, "amount": 100.0, "items": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


# --- Test: Payment failed — user not found ---
async def test_process_payment_user_not_found(client, mock_http_client):
    """Пользователь не найден — payment.failed."""
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 404
    mock_http_client.get = AsyncMock(return_value=mock_resp)

    resp = await client.post(
        "/api/payments",
        json={"order_id": 1, "user_id": 999, "amount": 100.0, "items": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


# --- Test: Receipt created in DB ---
def test_receipt_created(db_session):
    receipt = Receipt(
        order_id=1, user_id=1, total=Decimal("150.00"),
        items=[{"product_id": 1, "quantity": 2}],
    )
    db_session.add(receipt)
    db_session.commit()
    db_session.refresh(receipt)

    assert receipt.id is not None
    assert receipt.total == Decimal("150.00")
    assert receipt.email_sent == "pending"
