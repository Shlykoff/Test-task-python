"""WebSocket route for notifications."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import verify_token
from app.core.websocket import manager

logger = logging.getLogger("notification-service")

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket для уведом.
    Подключение: ws://host/ws/notifications?token=<jwt>
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    user_id = await verify_token(token)
    if not user_id:
        await websocket.close(code=4003, reason="Invalid token")
        return

    logger.info("WebSocket connected: user_id=%s", user_id)
    await manager.connect(websocket, user_id)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user_id=%s", user_id)
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.warning("WebSocket error: user_id=%s error=%s", user_id, e)
        manager.disconnect(websocket, user_id)
