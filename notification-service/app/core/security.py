"""JWT verification for notification-service."""

import logging
from typing import Optional

from app.config import JWT_ALGORITHM, JWT_PUBLIC_KEY_PEM, AUTH_SERVICE_URL
from app.dependencies import get_http_client

logger = logging.getLogger("notification-service")


async def verify_token(token: str) -> Optional[str]:
    """
    Verify JWT: first locally via RS256 public key, fallback → HTTP to auth-service.
    """
    # 1. Try local via RS256 public key
    if JWT_PUBLIC_KEY_PEM:
        try:
            from jose import jwt as jose_jwt
            payload = jose_jwt.decode(token, JWT_PUBLIC_KEY_PEM, algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                return payload.get("sub")
        except Exception as e:
            logger.debug("Local JWT verification failed: %s", e)

    # 2. Fallback: HTTP к auth-service
    try:
        http_client = await get_http_client()
        resp = await http_client.post(
            f"{AUTH_SERVICE_URL}/api/verify",
            json={"token": token},
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("valid"):
                return data.get("user_id")
    except Exception as e:
        logger.warning("Auth service verify fallback failed: %s", e, exc_info=True)
    return None
