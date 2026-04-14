"""Product SQLAlchemy model."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    cost_price = Column(Numeric(15, 2), nullable=False, index=True)
    quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
