"""Notification Service — Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationMessage(BaseModel):
    type: str
    data: dict
    timestamp: datetime


class TokenVerificationRequest(BaseModel):
    token: str


class TokenVerificationResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None


class PublishNotificationRequest(BaseModel):
    user_id: str
    type: str
    data: dict = {}
