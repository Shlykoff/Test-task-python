"""Auth routes — register, login, refresh, verify."""

import logging

from fastapi import APIRouter, HTTPException, status
from httpx import AsyncClient

from app.config import USER_SERVICE_URL, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.dependencies import get_http_client
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    RefreshResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)

logger = logging.getLogger("auth-service")

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Регистрация: создаёт пользователя через user-service, выдаёт JWT."""
    logger.info("Register request: username=%s email=%s", body.username, body.email)

    http_client = await get_http_client()
    try:
        resp = await http_client.post(
            f"{USER_SERVICE_URL}/api/users",
            json={
                "username": body.username,
                "email": body.email,
                "password": body.password,
            },
        )
    except Exception as e:
        logger.error("User service unavailable: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail="User service unavailable")

    if resp.status_code == 409:
        logger.warning(
            "Registration conflict: username=%s already exists", body.username
        )
        raise HTTPException(status_code=409, detail="Username or email already exists")
    if resp.status_code != 201:
        logger.error(
            "Failed to create user: status=%s response=%s", resp.status_code, resp.text
        )
        raise HTTPException(status_code=500, detail="Failed to create user")

    user_data = resp.json()

    access_token = create_access_token(
        {"sub": str(user_data["id"]), "username": user_data["username"]}
    )
    refresh_token = create_refresh_token({"sub": str(user_data["id"])})

    logger.info(
        "User registered: user_id=%s username=%s", user_data["id"], body.username
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/token", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Логин: проверяет пароль через user-service, выдаёт JWT."""
    logger.info("Login request: username=%s", body.username)

    http_client = await get_http_client()
    try:
        resp = await http_client.post(
            f"{USER_SERVICE_URL}/api/users/verify-password",
            json={"username": body.username, "password": body.password},
        )
    except Exception as e:
        logger.error("User service unavailable: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail="User service unavailable")

    if resp.status_code != 200:
        logger.warning(
            "Login failed: username=%s invalid credentials", body.username
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_data = resp.json()

    access_token = create_access_token(
        {"sub": str(user_data["user_id"]), "username": user_data["username"]}
    )
    refresh_token = create_refresh_token({"sub": str(user_data["user_id"])})

    logger.info(
        "User logged in: user_id=%s username=%s",
        user_data["user_id"],
        body.username,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(body: RefreshRequest):
    """Обновление access-токена по refresh-токену."""
    payload = decode_token(body.refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    http_client = await get_http_client()
    try:
        resp = await http_client.get(f"{USER_SERVICE_URL}/api/users/{user_id}")
    except Exception as e:
        logger.error("User service unavailable: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail="User service unavailable")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="User not found")

    user_data = resp.json()

    access_token = create_access_token({"sub": user_id, "username": user_data["username"]})
    logger.info("Token refreshed: user_id=%s", user_id)
    return RefreshResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/verify", response_model=VerifyTokenResponse)
async def verify_token(body: VerifyTokenRequest):
    """Проверка валидности JWT. Используется другими сервисами."""
    payload = decode_token(body.token, expected_type="access")
    if not payload:
        return VerifyTokenResponse(valid=False)

    return VerifyTokenResponse(
        valid=True,
        user_id=payload.get("sub"),
        username=payload.get("username"),
    )
