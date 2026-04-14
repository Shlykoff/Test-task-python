"""User SQLAlchemy model."""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    balance = Column(Numeric(15, 2), default=0.0)
    created_at = Column(DateTime, server_default=func.now())
