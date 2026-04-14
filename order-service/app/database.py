"""Database setup."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    total = Column(Numeric(15, 2), default=0.0)
    status = Column(String(20), default="pending")  # pending, paid, cancelled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(String(255), nullable=True)
    idempotency_key = Column(String(255), nullable=True, unique=True)


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, nullable=False)
    product_name = Column(String(255))
    quantity = Column(Integer, nullable=False)
    price_paid = Column(Numeric(15, 2), nullable=False)
