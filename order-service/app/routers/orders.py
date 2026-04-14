"""Order routes."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from httpx import AsyncClient
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import (
    CART_SERVICE_URL, PRODUCT_SERVICE_URL, JWT_ALGORITHM, JWT_PUBLIC_KEY_PEM,
)
from app.dependencies import get_db, get_http_client
from app.database import Order, OrderItem
from app.schemas.order import (
    CreateOrderRequest,
    OrderItemResponse,
    OrderResponse,
    OrderAcceptedResponse,
)
from app.core.messaging import publish_event

logger = logging.getLogger("order-service")

router = APIRouter(prefix="/api", tags=["orders"])

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, JWT_PUBLIC_KEY_PEM, algorithms=[JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        username = payload.get("username")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": int(user_id), "username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _build_order_response(order: Order, db: Session) -> OrderResponse:
    order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total=order.total,
        status=order.status,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=oi.id,
                product_id=oi.product_id,
                product_name=oi.product_name,
                quantity=oi.quantity,
                price_paid=oi.price_paid,
            )
            for oi in order_items
        ],
    )


@router.post(
    "/orders/create",
    response_model=OrderAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_order(
    body: CreateOrderRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """Оформить заказ (Saga)."""
    user_id = user["user_id"]
    logger.info("Create order request: user_id=%s", user_id)

    # Idempotency
    idempotency_key = x_idempotency_key
    if idempotency_key:
        existing = db.query(Order).filter(
            Order.idempotency_key == idempotency_key
        ).first()
        if existing:
            logger.info(
                "Idempotent hit: idempotency_key=%s order_id=%s",
                idempotency_key, existing.id,
            )
            return OrderAcceptedResponse(
                order_id=existing.id, status=existing.status
            )

    cart_session_id = body.session_id
    if not cart_session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # Get cart
    http_client = await get_http_client()
    try:
        cart_resp = await http_client.get(
            f"{CART_SERVICE_URL}/api/cart",
            headers={"X-Session-Id": cart_session_id},
        )
        if cart_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Cannot retrieve cart")
        cart_data = cart_resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cart service error: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail="Cart service unavailable")

    items = cart_data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Check stock
    for item in items:
        try:
            resp = await http_client.get(
                f"{PRODUCT_SERVICE_URL}/api/products/{item['product_id']}"
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=400, detail=f"Product {item['product_id']} not found"
                )
            product = resp.json()
            if product["quantity"] < item["quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Insufficient stock for {product['name']}: "
                        f"available {product['quantity']}, requested {item['quantity']}"
                    ),
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Product service error: product_id=%s error=%s",
                item["product_id"], e, exc_info=True,
            )
            raise HTTPException(
                status_code=503, detail="Product service unavailable"
            )

    total = sum(
        Decimal(str(item["user_price"])) * item["quantity"] for item in items
    )

    # Create Order(status=pending)
    order = Order(
        user_id=user_id,
        total=total,
        status="pending",
        session_id=cart_session_id,
        idempotency_key=idempotency_key,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    for item in items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            product_name=item["product_name"],
            quantity=item["quantity"],
            price_paid=item["user_price"],
        ))
    db.commit()

    logger.info(
        "Order created: order_id=%s user_id=%s total=%s status=pending",
        order.id, user_id, total,
    )

    # Publish order.created
    order_items_list = [
        {
            "product_id": i["product_id"],
            "product_name": i["product_name"],
            "quantity": i["quantity"],
            "user_price": float(i["user_price"]),
        }
        for i in items
    ]
    published = await publish_event("order_events", "order.created", {
        "order_id": order.id,
        "user_id": user_id,
        "total": float(total),
        "items": order_items_list,
        "session_id": cart_session_id,
    })
    if not published:
        logger.error("Failed to publish order.created for order_id=%s", order.id)

    return OrderAcceptedResponse(order_id=order.id, status="pending")


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    user: dict = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Мои заказы. Пагинация: skip/limit."""
    orders = (
        db.query(Order)
        .filter(Order.user_id == user["user_id"])
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(min(limit, 100))
        .all()
    )
    return [_build_order_response(o, db) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Детали заказа."""
    order = db.query(Order).filter(
        Order.id == order_id, Order.user_id == user["user_id"]
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _build_order_response(order, db)


@router.get("/orders/{order_id}/status", response_model=OrderAcceptedResponse)
async def get_order_status(
    order_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Статус заказа (для polling после 202)."""
    order = db.query(Order).filter(
        Order.id == order_id, Order.user_id == user["user_id"]
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderAcceptedResponse(order_id=order.id, status=order.status)
