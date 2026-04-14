"""RabbitMQ consumer for notification-service."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.config import RABBITMQ_URL, RABBITMQ_AVAILABLE
from app.database import SessionLocal, Notification
from app.core.websocket import manager

logger = logging.getLogger("notification-service")

try:
    import aio_pika
    RABBIT_AVAILABLE = True
except ImportError:
    RABBIT_AVAILABLE = False


async def consume_rabbitmq():
    """Слушать события из RabbitMQ и пушить в WebSocket."""
    if not RABBIT_AVAILABLE or not RABBITMQ_AVAILABLE:
        logger.warning("RabbitMQ not available, notification consumer not started")
        return

    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()

        order_exchange = await channel.declare_exchange(
            "order_events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        payment_exchange = await channel.declare_exchange(
            "payment_events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        notification_exchange = await channel.declare_exchange(
            "notification_events", aio_pika.ExchangeType.FANOUT, durable=True
        )

        notification_queue = await channel.declare_queue("notifications", exclusive=True)

        await notification_queue.bind(order_exchange, routing_key="order.created")
        await notification_queue.bind(order_exchange, routing_key="order.paid")
        await notification_queue.bind(order_exchange, routing_key="order.cancelled")
        await notification_queue.bind(payment_exchange, routing_key="payment.completed")
        await notification_queue.bind(payment_exchange, routing_key="payment.failed")
        await notification_queue.bind(notification_exchange)

        logger.info("Notification consumer started: queue=notifications")

        async with notification_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        user_id = body.get("user_id")
                        if user_id:
                            notification_data = {
                                "type": message.routing_key or "unknown",
                                "data": body,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                            logger.info(
                                "Received event: type=%s user_id=%s",
                                message.routing_key, user_id,
                            )

                            db = SessionLocal()
                            try:
                                notif = Notification(
                                    user_id=str(user_id),
                                    type=message.routing_key or "unknown",
                                    data=body,
                                    created_at=datetime.now(timezone.utc),
                                )
                                db.add(notif)
                                db.commit()
                            except Exception as e:
                                db.rollback()
                                logger.error(
                                    "Failed to save notification: %s", e, exc_info=True
                                )
                            finally:
                                db.close()

                            await manager.send_personal(str(user_id), notification_data)
                        else:
                            logger.warning("Received message without user_id: %s", body)
                    except KeyError as e:
                        logger.error("Malformed message, missing key=%s", e)
                    except Exception as e:
                        logger.error(
                            "Error processing RabbitMQ message: %s", e, exc_info=True
                        )
    except Exception as e:
        logger.error(
            "RabbitMQ consumer connection error: %s", e, exc_info=True
        )
        await asyncio.sleep(5)
        asyncio.create_task(consume_rabbitmq())
