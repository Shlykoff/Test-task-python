"""Product Service — Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Annotated

from pydantic import BaseModel, Field, PlainSerializer


JSONDecimal = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    cost_price: JSONDecimal = Field(..., gt=0)
    quantity: int = Field(default=0, ge=0)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    cost_price: JSONDecimal
    quantity: int
    user_price: JSONDecimal
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cost_price: Optional[JSONDecimal] = None
    quantity: Optional[int] = None


class StockReserveRequest(BaseModel):
    product_id: int
    quantity: int


class StockReserveResponse(BaseModel):
    success: bool
    product_id: int
    remaining_quantity: int
