"""Billing service business logic — payment processing."""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import USER_SERVICE_URL
from app.dependencies import get_http_client
from app.database import Receipt

logger = logging.getLogger("billing-service")


async def process_payment_core(
    order_id: int,
    user_id: int,
    amount: Decimal,
    items: list,
    db: Session,
) -> dict:
    """
    Core payment processing: check balance → deduct → create receipt.
    Called from both HTTP endpoint and RabbitMQ consumer.
    """
    logger.info(
        "Processing payment: order_id=%s user_id=%s amount=%s",
        order_id, user_id, amount,
    )

    http_client = await get_http_client()

    # 1. Check balance
    try:
        resp = await http_client.get(f"{USER_SERVICE_URL}/api/users/{user_id}")
        if resp.status_code != 200:
            logger.warning(
                "User not found: user_id=%s, status=%s", user_id, resp.status_code
            )
            return {"success": False, "order_id": order_id}
        user_data = resp.json()
    except Exception as e:
        logger.error(
            "Failed to fetch user balance: user_id=%s error=%s", user_id, e, exc_info=True
        )
        return {"success": False, "order_id": order_id}

    if Decimal(str(user_data["balance"])) < amount:
        logger.warning(
            "Insufficient balance: user_id=%s balance=%s amount=%s",
            user_id, user_data["balance"], amount,
        )
        return {"success": False, "order_id": order_id}

    # 2. Deduct balance
    try:
        resp = await http_client.post(
            f"{USER_SERVICE_URL}/api/users/{user_id}/deduct",
            json={"amount": float(amount)},
        )
        if resp.status_code != 200:
            logger.warning("Deduct failed: user_id=%s status=%s", user_id, resp.status_code)
            return {"success": False, "order_id": order_id}
    except Exception as e:
        logger.error(
            "Failed to deduct balance: user_id=%s error=%s", user_id, e, exc_info=True
        )
        return {"success": False, "order_id": order_id}

    # 3. Create receipt
    receipt = Receipt(
        order_id=order_id,
        user_id=user_id,
        total=amount,
        items=items,
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # 4. Mark receipt as sent
    receipt.email_sent = "sent"
    db.commit()

    logger.info("Payment successful: order_id=%s receipt_id=%s", order_id, receipt.id)
    return {"success": True, "order_id": order_id, "receipt_id": receipt.id}
