"""Notification routes."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.database import Notification
from app.schemas.notification import PublishNotificationRequest

logger = logging.getLogger("notification-service")

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications/{user_id}")
async def get_user_notifications(
    user_id: str, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)
):
    """Получить историю уведомлений пользователя. Пагинация: skip/limit."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == str(user_id))
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "data": n.data,
            "timestamp": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.post("/notifications/publish", status_code=201)
async def publish_notification(
    body: PublishNotificationRequest, db: Session = Depends(get_db)
):
    """Опубликовать тестовое уведомление (для тестов/отладки)."""
    notif = Notification(
        user_id=body.user_id,
        type=body.type,
        data=body.data,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    from app.core.websocket import manager
    await manager.send_personal(body.user_id, {
        "type": body.type,
        "data": body.data,
        "timestamp": notif.created_at.isoformat(),
    })

    return {"id": notif.id, "status": "created"}


@router.delete("/notifications/{user_id}")
async def clear_user_notifications(user_id: str, db: Session = Depends(get_db)):
    """Очистить историю уведомлений пользователя."""
    db.query(Notification).filter(Notification.user_id == str(user_id)).delete()
    db.commit()
    return {"status": "cleared"}
