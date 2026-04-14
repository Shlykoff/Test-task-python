"""Billing Service — Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Annotated

from pydantic import BaseModel, PlainSerializer


JSONDecimal = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]


class PaymentRequest(BaseModel):
    order_id: int
    user_id: int
    amount: JSONDecimal
    items: list = []


class PaymentResponse(BaseModel):
    success: bool
    order_id: int
    receipt_id: Optional[int] = None


class ReceiptResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    total: JSONDecimal
    items: Optional[list]
    created_at: datetime
    email_sent: str
