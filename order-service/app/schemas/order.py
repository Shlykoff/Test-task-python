"""Order Service — Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Annotated

from pydantic import BaseModel, PlainSerializer


JSONDecimal = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]


class CreateOrderRequest(BaseModel):
    session_id: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    price_paid: JSONDecimal


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total: JSONDecimal
    status: str
    created_at: datetime
    items: list[OrderItemResponse] = []
    model_config = {"from_attributes": True}


class OrderAcceptedResponse(BaseModel):
    order_id: int
    status: str
