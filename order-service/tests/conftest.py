"""
Test configuration for order-service.
Uses dedicated PostgreSQL test container with transaction rollback.
"""

import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
from app.dependencies import get_db
from app.routers.orders import get_current_user

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@postgres-test:5432/orders")
os.environ.setdefault("APP_VERSION", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")
os.environ.setdefault("RABBITMQ_AVAILABLE", "false")

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@postgres-test:5432/orders"
test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before tests, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """
    Provide a transactional database session that rolls back after each test.
    """
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

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
