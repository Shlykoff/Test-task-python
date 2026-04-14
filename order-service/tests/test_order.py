"""Тесты order-service — бизнес-логика и модели. Используют PostgreSQL test container."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, Order, OrderItem
from app.dependencies import get_db
from app.routers.orders import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

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


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "order-service"


# --- DB Logic ---
def test_create_order_in_db(db_session):
    """Проверка создания заказа в БД напрямую."""
    order = Order(user_id=1, total=426.0, status="paid", session_id="test-session")
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    item = OrderItem(
        order_id=order.id,
        product_id=3,
        product_name="AirPods Pro 2",
        quantity=2,
        price_paid=180.0,
    )
    db_session.add(item)
    db_session.commit()

    saved_order = db_session.query(Order).filter(Order.id == order.id).first()
    assert saved_order is not None
    assert saved_order.total == 426.0
    assert saved_order.status == "paid"

    items = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    assert len(items) == 1
    assert items[0].product_name == "AirPods Pro 2"


def test_list_orders_for_user(db_session):
    """Проверка фильтрации заказов по user_id."""
    db_session.add(Order(user_id=1, total=100.0, status="paid"))
    db_session.add(Order(user_id=1, total=200.0, status="paid"))
    db_session.add(Order(user_id=2, total=300.0, status="paid"))
    db_session.commit()

    user1_orders = db_session.query(Order).filter(Order.user_id == 1).all()
    assert len(user1_orders) == 2
    assert all(o.user_id == 1 for o in user1_orders)

    user2_orders = db_session.query(Order).filter(Order.user_id == 2).all()
    assert len(user2_orders) == 1


def test_order_statuses(db_session):
    """Проверка статусов заказа."""
    pending = Order(user_id=1, total=100.0, status="pending")
    paid = Order(user_id=1, total=200.0, status="paid")
    cancelled = Order(user_id=1, total=300.0, status="cancelled")
    db_session.add_all([pending, paid, cancelled])
    db_session.commit()

    assert pending.status == "pending"
    assert paid.status == "paid"
    assert cancelled.status == "cancelled"


def test_order_timestamps(db_session):
    """Проверка automatic created_at."""
    order = Order(user_id=1, total=100.0)
    db_session.add(order)
    db_session.commit()

    assert order.created_at is not None
    assert isinstance(order.created_at, datetime)
