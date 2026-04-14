"""
Test configuration for user-service.
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

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@postgres-test:5432/users")
os.environ.setdefault("APP_VERSION", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")

TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@postgres-test:5432/users"
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
    This ensures test isolation - no data leaks between tests.
    """
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
