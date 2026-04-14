"""Cart Service — Pydantic schemas."""

from decimal import Decimal
from typing import Optional, Annotated

from pydantic import BaseModel, Field, PlainSerializer


JSONDecimal = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    user_price: JSONDecimal


class CartResponse(BaseModel):
    session_id: str
    items: list[CartItemResponse]
    total: JSONDecimal
