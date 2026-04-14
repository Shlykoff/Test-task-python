"""RabbitMQ messaging for order-service — publish, consumers, saga timeout."""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import (
    RABBITMQ_URL, RABBITMQ_AVAILABLE, PRODUCT_SERVICE_URL,
    CART_SERVICE_URL, USER_SERVICE_URL, SAGA_TIMEOUT_SECONDS,
)
from app.database import SessionLocal, Order, OrderItem
from app.dependencies import get_http_client, _http_client

logger = logging.getLogger("order-service")

# Track if RabbitMQ should be used
try:
    import aio_pika
    RABBIT_AVAILABLE = True
except ImportError:
    RABBIT_AVAILABLE = False


async def publish_event(exchange_name: str, routing_key: str, message: dict):
    """Publish event to RabbitMQ."""
    if not RABBIT_AVAILABLE or not RABBITMQ_AVAILABLE:
        logger.warning(
            "RabbitMQ not available, skipping publish: exchange=%s routing_key=%s",
            exchange_name, routing_key,
        )
        return False
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
            )
            await exchange.publish(
                aio_pika.Message(body=json.dumps(message).encode()),
                routing_key=routing_key,
            )
        logger.info(
            "Published event: exchange=%s routing_key=%s order_id=%s",
            exchange_name, routing_key, message.get("order_id"),
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to publish event: exchange=%s routing_key=%s error=%s",
            exchange_name, routing_key, e, exc_info=True,
        )
        return False


async def consume_payment_completed():
    """payment.completed → reserve stock → update status=paid → clear cart → publish order.paid."""
    if not RABBIT_AVAILABLE or not RABBITMQ_AVAILABLE:
        logger.warning("RabbitMQ not available, payment_completed consumer not started")
        return
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                "payment_events", aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue("order_payments", durable=True)
            await queue.bind(exchange, routing_key="payment.completed")

            logger.info("Order consumer started: queue=order_payments, routing_key=payment.completed")

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = json.loads(message.body.decode())
                            order_id = body["order_id"]
                            user_id = body["user_id"]

                            logger.info(
                                "Received payment.completed: order_id=%s user_id=%s",
                                order_id, user_id,
                            )

                            db = SessionLocal()
                            try:
                                order = db.query(Order).filter(
                                    Order.id == order_id
                                ).first()
                                if not order or order.status != "pending":
                                    logger.warning(
                                        "Order not found or not pending: order_id=%s status=%s",
                                        order_id, order.status if order else "None",
                                    )
                                    continue

                                items = db.query(OrderItem).filter(
                                    OrderItem.order_id == order_id
                                ).all()

                                all_reserved = True
                                for item in items:
                                    try:
                                        http_client = await get_http_client()
                                        resp = await http_client.post(
                                            f"{PRODUCT_SERVICE_URL}/api/products/reserve-stock",
                                            json={
                                                "product_id": item.product_id,
                                                "quantity": item.quantity,
                                            },
                                        )
                                        if resp.status_code != 200 or not resp.json().get("success"):
                                            logger.warning(
                                                "Reserve stock failed: product_id=%s qty=%s",
                                                item.product_id, item.quantity,
                                            )
                                            all_reserved = False
                                            break
                                    except Exception as e:
                                        logger.error(
                                            "Reserve stock HTTP error: product_id=%s error=%s",
                                            item.product_id, e, exc_info=True,
                                        )
                                        all_reserved = False
                                        break

                                if all_reserved:
                                    order.status = "paid"
                                    db.commit()
                                    logger.info("Order paid: order_id=%s", order_id)
                                    try:
                                        http_client = await get_http_client()
                                        await http_client.delete(
                                            f"{CART_SERVICE_URL}/api/cart",
                                            headers={"X-Session-Id": order.session_id},
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            "Failed to clear cart: order_id=%s error=%s",
                                            order_id, e,
                                        )
                                    await publish_event(
                                        "order_events", "order.paid", {
                                            "order_id": order.id,
                                            "user_id": user_id,
                                            "total": float(order.total),
                                        }
                                    )
                                else:
                                    logger.warning("Reserve failed, refunding: order_id=%s", order_id)
                                    try:
                                        http_client = await get_http_client()
                                        await http_client.post(
                                            f"{USER_SERVICE_URL}/api/users/{user_id}/topup",
                                            json={"amount": float(order.total)},
                                        )
                                    except Exception as e:
                                        logger.error(
                                            "Refund failed: order_id=%s error=%s",
                                            order_id, e, exc_info=True,
                                        )
                                    order.status = "cancelled"
                                    db.commit()
                            finally:
                                db.close()
                        except KeyError as e:
                            logger.error("Malformed payment.completed message, missing key=%s", e)
                        except Exception as e:
                            logger.error(
                                "Error processing payment.completed: error=%s", e, exc_info=True
                            )
    except Exception as e:
        logger.error(
            "Payment completed consumer connection error: %s", e, exc_info=True
        )
        await asyncio.sleep(5)
        asyncio.create_task(consume_payment_completed())


async def consume_payment_failed():
    """payment.failed → update status=cancelled."""
    if not RABBIT_AVAILABLE or not RABBITMQ_AVAILABLE:
        logger.warning("RabbitMQ not available, payment_failed consumer not started")
        return
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                "payment_events", aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue("order_payments_failed", durable=True)
            await queue.bind(exchange, routing_key="payment.failed")

            logger.info(
                "Order consumer started: queue=order_payments_failed, routing_key=payment.failed"
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = json.loads(message.body.decode())
                            order_id = body["order_id"]

                            logger.info(
                                "Received payment.failed: order_id=%s reason=%s",
                                order_id, body.get("reason"),
                            )

                            db = SessionLocal()
                            try:
                                order = db.query(Order).filter(Order.id == order_id).first()
                                if order and order.status == "pending":
                                    order.status = "cancelled"
                                    db.commit()
                                    logger.info("Order cancelled: order_id=%s", order_id)
                                else:
                                    logger.warning(
                                        "Order not found or not pending: order_id=%s", order_id
                                    )
                            finally:
                                db.close()
                        except KeyError as e:
                            logger.error("Malformed payment.failed message, missing key=%s", e)
                        except Exception as e:
                            logger.error(
                                "Error processing payment.failed: error=%s", e, exc_info=True
                            )
    except Exception as e:
        logger.error(
            "Payment failed consumer connection error: %s", e, exc_info=True
        )
        await asyncio.sleep(5)
        asyncio.create_task(consume_payment_failed())


async def saga_timeout_checker():
    """Periodically check for stuck orders in pending status and cancel them."""
    while True:
        try:
            await asyncio.sleep(60)  # Every minute

            db = SessionLocal()
            try:
                timeout_threshold = datetime.now(timezone.utc) - timedelta(
                    seconds=SAGA_TIMEOUT_SECONDS
                )
                stuck_orders = db.query(Order).filter(
                    Order.status == "pending",
                    Order.created_at < timeout_threshold,
                ).all()

                for order in stuck_orders:
                    logger.warning(
                        "Saga timeout: cancelling order_id=%s (pending for >%s sec)",
                        order.id, SAGA_TIMEOUT_SECONDS,
                    )
                    order.status = "cancelled"
                    db.commit()

                    await publish_event("order_events", "order.cancelled", {
                        "order_id": order.id,
                        "user_id": order.user_id,
                        "reason": "saga_timeout",
                    })

                if stuck_orders:
                    logger.info(
                        "Saga timeout checker: cancelled %d orders", len(stuck_orders)
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error("Saga timeout checker error: %s", e, exc_info=True)
