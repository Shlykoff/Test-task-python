"""Billing routes."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.database import Receipt
from app.schemas.billing import PaymentRequest, PaymentResponse, ReceiptResponse
from app.services.billing import process_payment_core

logger = logging.getLogger("billing-service")

router = APIRouter(prefix="/api", tags=["billing"])


@router.post("/payments", response_model=PaymentResponse)
async def process_payment_http(body: PaymentRequest, db: Session = Depends(get_db)):
    """Обработать оплату через HTTP (альтернатива Saga — для ручных операций)."""
    logger.info(
        "HTTP payment request: order_id=%s user_id=%s amount=%s",
        body.order_id, body.user_id, body.amount,
    )
    result = await process_payment_core(
        body.order_id, body.user_id, body.amount, body.items, db
    )
    if not result["success"]:
        logger.warning("HTTP payment failed: order_id=%s", body.order_id)
    return result


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """Получить чек."""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.get("/receipts/order/{order_id}", response_model=list[ReceiptResponse])
async def get_receipts_by_order(order_id: int, db: Session = Depends(get_db)):
    """Чеки по заказу."""
    receipts = db.query(Receipt).filter(Receipt.order_id == order_id).all()
    return receipts
