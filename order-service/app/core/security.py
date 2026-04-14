"""JWT verification for order-service."""

from typing import Optional

from jose import jwt, JWTError

from app.config import JWT_ALGORITHM, JWT_PUBLIC_KEY_PEM


async def get_current_user_from_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, JWT_PUBLIC_KEY_PEM, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        username = payload.get("username")
        if not user_id:
            return None
        return {"user_id": int(user_id), "username": username}
    except JWTError:
        return None
