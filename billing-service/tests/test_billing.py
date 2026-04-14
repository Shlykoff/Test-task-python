"""Тесты billing-service — бизнес-логика и модели. Используют PostgreSQL test container."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, Receipt
from app.dependencies import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

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


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "billing-service"


# --- DB Logic ---
def test_create_receipt_in_db(db_session):
    """Проверка создания чека в БД напрямую."""
    receipt = Receipt(
        order_id=1,
        user_id=1,
        total=426.0,
        items=[{"product_id": 3, "quantity": 2, "price": 180.0}],
    )
    db_session.add(receipt)
    db_session.commit()
    db_session.refresh(receipt)

    assert receipt.id is not None
    assert receipt.order_id == 1
    assert receipt.total == 426.0
    assert receipt.email_sent == "pending"


def test_receipt_timestamps(db_session):
    """Проверка automatic created_at."""
    receipt = Receipt(order_id=2, user_id=1, total=100.0)
    db_session.add(receipt)
    db_session.commit()

    assert receipt.created_at is not None
    assert isinstance(receipt.created_at, datetime)


def test_receipt_filtering(db_session):
    """Фильтрация чеков по order_id."""
    db_session.add_all([
        Receipt(order_id=1, user_id=1, total=100.0),
        Receipt(order_id=1, user_id=1, total=200.0),
        Receipt(order_id=2, user_id=1, total=300.0),
    ])
    db_session.commit()

    order1_receipts = db_session.query(Receipt).filter(Receipt.order_id == 1).all()
    assert len(order1_receipts) == 2

    order2_receipts = db_session.query(Receipt).filter(Receipt.order_id == 2).all()
    assert len(order2_receipts) == 1


# --- API ---
async def test_get_receipt_not_found(client):
    resp = await client.get("/api/receipts/9999")
    assert resp.status_code == 404


async def test_get_receipts_by_order_empty(client):
    resp = await client.get("/api/receipts/order/9999")
    assert resp.status_code == 200
    assert resp.json() == []
