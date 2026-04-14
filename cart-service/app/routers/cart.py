"""Cart routes."""

import asyncio
import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status, Request, Response

from app.dependencies import get_session_id, set_session_cookie, get_http_client
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse, CartItemResponse
from app.services.cart import (
    get_cart_data, save_cart, fetch_product_info, verify_product_exists, cart_key,
)
from app.core.redis import redis_client

logger = logging.getLogger("cart-service")

router = APIRouter(prefix="/api", tags=["cart"])


@router.get("/cart", response_model=CartResponse)
async def get_cart(request: Request, response: Response):
    """Получить корзину. Создаёт session_id, если нет."""
    session_id = get_session_id(request)
    set_session_cookie(response, session_id)

    cart_data = get_cart_data(session_id)
    if not cart_data:
        return CartResponse(session_id=session_id, items=[], total=Decimal("0.00"))

    tasks = [fetch_product_info(pid, qty) for pid, qty in cart_data.items()]
    results = await asyncio.gather(*tasks)

    items = [r for r in results if r is not None]
    total = sum(item["user_price"] * item["quantity"] for item in items)

    return CartResponse(
        session_id=session_id,
        items=[CartItemResponse(**item) for item in items],
        total=round(total, 2),
    )


@router.post("/cart/items", status_code=status.HTTP_201_CREATED)
async def add_item(body: CartItemAdd, request: Request, response: Response):
    """Добавить товар в корзину."""
    session_id = get_session_id(request)
    set_session_cookie(response, session_id)

    product = await verify_product_exists(body.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    cart_data = get_cart_data(session_id)
    cart_data[body.product_id] = cart_data.get(body.product_id, 0) + body.quantity
    save_cart(session_id, cart_data)

    return {"session_id": session_id, "product_id": body.product_id, "quantity": cart_data[body.product_id]}


@router.patch("/cart/items/{product_id}")
async def update_item(product_id: int, body: CartItemUpdate, request: Request, response: Response):
    """Изменить количество позиции."""
    session_id = get_session_id(request)
    set_session_cookie(response, session_id)

    cart_data = get_cart_data(session_id)
    if product_id not in cart_data:
        raise HTTPException(status_code=404, detail="Item not in cart")

    cart_data[product_id] = body.quantity
    save_cart(session_id, cart_data)

    return {"session_id": session_id, "product_id": product_id, "quantity": body.quantity}


@router.delete("/cart/items/{product_id}")
async def remove_item(product_id: int, request: Request, response: Response):
    """Удалить позицию из корзины."""
    session_id = get_session_id(request)
    set_session_cookie(response, session_id)

    cart_data = get_cart_data(session_id)
    if product_id not in cart_data:
        raise HTTPException(status_code=404, detail="Item not in cart")

    del cart_data[product_id]
    save_cart(session_id, cart_data)

    return {"status": "deleted", "product_id": product_id}


@router.delete("/cart")
async def clear_cart(request: Request, response: Response):
    """Очистить корзину."""
    session_id = get_session_id(request)
    response.delete_cookie("session_id")
    redis_client.delete(cart_key(session_id))
    return {"status": "cleared"}


@router.post("/cart/merge")
async def merge_cart(session_id: str, request: Request, response: Response):
    """Мерджить корзину сессии с корзиной пользователя по session_id."""
    user_session_id = get_session_id(request)
    set_session_cookie(response, user_session_id)

    source_cart = get_cart_data(session_id)
    target_cart = get_cart_data(user_session_id)

    for product_id, quantity in source_cart.items():
        target_cart[product_id] = target_cart.get(product_id, 0) + quantity

    save_cart(user_session_id, target_cart)
    redis_client.delete(cart_key(session_id))

    return {"status": "merged", "session_id": user_session_id}
