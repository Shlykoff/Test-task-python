"""Cart service business logic — Redis operations, product fetching."""

import asyncio
import logging
from decimal import Decimal
from typing import Optional

from app.config import CART_TTL_SECONDS
from app.core.redis import redis_client
from app.dependencies import get_http_client
from app.config import PRODUCT_SERVICE_URL

logger = logging.getLogger("cart-service")


def cart_key(session_id: str) -> str:
    return f"cart:{session_id}"


def get_cart_data(session_id: str) -> dict:
    data = redis_client.hgetall(cart_key(session_id))
    return {int(k): int(v) for k, v in data.items()}


def save_cart(session_id: str, data: dict):
    key = cart_key(session_id)
    pipe = redis_client.pipeline()
    pipe.delete(key)
    if data:
        pipe.hset(key, mapping={str(k): str(v) for k, v in data.items()})
        pipe.expire(key, CART_TTL_SECONDS)
    pipe.execute()


async def fetch_product_info(product_id: int, quantity: int) -> Optional[dict]:
    """Fetch product info for a cart item."""
    try:
        http_client = await get_http_client()
        resp = await http_client.get(f"{PRODUCT_SERVICE_URL}/api/products/{product_id}")
        if resp.status_code == 200:
            product = resp.json()
            return {
                "product_id": product_id,
                "product_name": product["name"],
                "quantity": quantity,
                "user_price": Decimal(str(product["user_price"])),
            }
        logger.warning(
            "Product not found: product_id=%s status=%s", product_id, resp.status_code
        )
    except Exception as e:
        logger.error(
            "Failed to fetch product info: product_id=%s error=%s", product_id, e
        )
    return None


async def verify_product_exists(product_id: int):
    """Verify that a product exists and is available."""
    http_client = await get_http_client()
    try:
        resp = await http_client.get(f"{PRODUCT_SERVICE_URL}/api/products/{product_id}")
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None
