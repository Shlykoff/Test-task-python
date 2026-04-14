"""Database setup."""

from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, Numeric, DateTime, String, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    total = Column(Numeric(15, 2), nullable=False)
    items = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    email_sent = Column(String(10), default="pending")


class ProcessedEvent(Base):
    """Table for idempotency — tracking already processed events."""
    __tablename__ = "processed_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    order_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
