"""User Service — Pydantic request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Annotated

from pydantic import BaseModel, Field, PlainSerializer


JSONDecimal = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    balance: JSONDecimal
    created_at: datetime

    model_config = {"from_attributes": True}


class VerifyPasswordRequest(BaseModel):
    username: str
    password: str


class VerifyPasswordResponse(BaseModel):
    valid: bool
    user_id: Optional[int] = None
    username: Optional[str] = None


class ProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    balance: JSONDecimal


class TopUpRequest(BaseModel):
    amount: JSONDecimal = Field(..., gt=0)


class BalanceResponse(BaseModel):
    user_id: int
    balance: JSONDecimal
