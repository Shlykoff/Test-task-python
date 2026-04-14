"""RabbitMQ messaging for billing-service — publish + consumer."""

import asyncio
import hashlib
import json
import logging
from decimal import Decimal

from app.config import RABBITMQ_URL, RABBITMQ_AVAILABLE
from app.database import SessionLocal, ProcessedEvent
from app.services.billing import process_payment_core

logger = logging.getLogger("billing-service")

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
        logger.info("Published event: exchange=%s routing_key=%s", exchange_name, routing_key)
        return True
    except Exception as e:
        logger.error(
            "Failed to publish event: exchange=%s routing_key=%s error=%s",
            exchange_name, routing_key, e, exc_info=True,
        )
        return False


async def consume_order_created():
    """
    Consumes order.created from RabbitMQ.
    Flow: check balance → deduct → create receipt → publish payment.completed/failed.
    """
    if not RABBIT_AVAILABLE or not RABBITMQ_AVAILABLE:
        logger.warning("RabbitMQ not available, consumer not started")
        return

    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                "order_events", aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await channel.declare_queue("billing_payments", durable=True)
            await queue.bind(exchange, routing_key="order.created")

            logger.info(
                "Billing consumer started: queue=billing_payments, routing_key=order.created"
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = json.loads(message.body.decode())
                            order_id = body["order_id"]
                            user_id = body["user_id"]
                            total = Decimal(str(body["total"]))
                            items = body.get("items", [])

                            # Idempotency check
                            event_id = hashlib.sha256(
                                json.dumps(body, sort_keys=True).encode()
                            ).hexdigest()

                            db = SessionLocal()
                            try:
                                existing = db.query(ProcessedEvent).filter(
                                    ProcessedEvent.event_id == event_id
                                ).first()
                                if existing:
                                    logger.info(
                                        "Duplicate event skipped: event_id=%s order_id=%s",
                                        event_id, order_id,
                                    )
                                    continue

                                logger.info(
                                    "Received order.created: order_id=%s user_id=%s total=%s",
                                    order_id, user_id, total,
                                )

                                result = await process_payment_core(
                                    order_id, user_id, total, items, db
                                )

                                if result["success"]:
                                    published = await publish_event(
                                        "payment_events", "payment.completed", {
                                            "order_id": order_id,
                                            "user_id": user_id,
                                            "amount": float(total),
                                            "receipt_id": result["receipt_id"],
                                        }
                                    )
                                    if not published:
                                        logger.error(
                                            "Failed to publish payment.completed for order_id=%s",
                                            order_id,
                                        )
                                else:
                                    published = await publish_event(
                                        "payment_events", "payment.failed", {
                                            "order_id": order_id,
                                            "user_id": user_id,
                                            "reason": "insufficient_balance_or_deduct_failed",
                                        }
                                    )
                                    if not published:
                                        logger.error(
                                            "Failed to publish payment.failed for order_id=%s",
                                            order_id,
                                        )

                                # Mark event as processed
                                db.add(ProcessedEvent(
                                    event_id=event_id,
                                    event_type="order.created",
                                    order_id=order_id,
                                ))
                                db.commit()
                            finally:
                                db.close()
                        except KeyError as e:
                            logger.error("Malformed message, missing key=%s: %s", e, body)
                        except Exception as e:
                            logger.error(
                                "Error processing order.created: error=%s", e, exc_info=True
                            )
    except Exception as e:
        logger.error(
            "RabbitMQ consumer connection error: %s", e, exc_info=True
        )
        await asyncio.sleep(5)
        asyncio.create_task(consume_order_created())
