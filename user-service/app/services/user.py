"""User service business logic."""

import logging
from decimal import Decimal

from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.models.user import User

logger = logging.getLogger("user-service")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_data(db: Session):
    """Создаёт тестового пользователя, если его нет."""
    user = db.query(User).filter(User.username == "testuser").first()
    if not user:
        user = User(
            username="testuser",
            email="testuser@example.com",
            password_hash=pwd_context.hash("testpassword"),
            balance=Decimal("10000.00"),
        )
        db.add(user)
        db.commit()
        logger.info("Seed data: testuser created")
