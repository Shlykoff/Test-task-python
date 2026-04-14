"""User routes — CRUD, balance, topup, deduct."""

import logging

from fastapi import APIRouter, HTTPException, Depends, status
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.user import User
from app.schemas.user import (
    CreateUserRequest,
    UserResponse,
    VerifyPasswordRequest,
    VerifyPasswordResponse,
    ProfileResponse,
    TopUpRequest,
    BalanceResponse,
)

logger = logging.getLogger("user-service")

router = APIRouter(prefix="/api", tags=["users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: CreateUserRequest, db: Session = Depends(get_db)):
    """Создание пользователя. Вызывается auth-service при регистрации."""
    existing = db.query(User).filter(
        (User.username == body.username) | (User.email == body.email)
    ).first()
    if existing:
        logger.warning(
            "User creation conflict: username=%s or email=%s already exists",
            body.username, body.email,
        )
        raise HTTPException(
            status_code=409, detail="Username or email already exists"
        )

    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_context.hash(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User created: user_id=%s username=%s", user.id, body.username)
    return user


@router.post("/users/verify-password", response_model=VerifyPasswordResponse)
async def verify_password(body: VerifyPasswordRequest, db: Session = Depends(get_db)):
    """Проверка пароля. Вызывается auth-service при логине."""
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return VerifyPasswordResponse(
        valid=True, user_id=user.id, username=user.username
    )


@router.get("/users/{user_id}/profile", response_model=ProfileResponse)
async def get_profile(user_id: int, db: Session = Depends(get_db)):
    """Профиль пользователя."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users/{user_id}/topup", response_model=BalanceResponse)
async def topup(user_id: int, body: TopUpRequest, db: Session = Depends(get_db)):
    """Пополнение баланса."""
    amount = body.amount
    logger.info("Topup request: user_id=%s amount=%s", user_id, amount)
    result = db.execute(
        update(User)
        .where(User.id == user_id)
        .values(balance=User.balance + amount)
    )
    db.commit()

    if result.rowcount == 0:
        logger.warning("Topup failed: user_id=%s not found", user_id)
        raise HTTPException(status_code=404, detail="User not found")

    user = db.query(User).filter(User.id == user_id).first()
    logger.info("Topup successful: user_id=%s new_balance=%s", user_id, user.balance)
    return {"user_id": user.id, "balance": user.balance}


@router.post("/users/{user_id}/deduct", response_model=BalanceResponse)
async def deduct(user_id: int, body: TopUpRequest, db: Session = Depends(get_db)):
    """Списание с баланса. Атомарная операция — защита от race condition."""
    amount = body.amount
    logger.info("Deduct request: user_id=%s amount=%s", user_id, amount)

    result = db.execute(
        update(User)
        .where(User.id == user_id, User.balance >= amount)
        .values(balance=User.balance - amount)
    )
    db.commit()

    if result.rowcount == 0:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("Deduct failed: user_id=%s not found", user_id)
            raise HTTPException(status_code=404, detail="User not found")
        logger.warning(
            "Deduct failed: user_id=%s insufficient balance", user_id
        )
        raise HTTPException(status_code=400, detail="Insufficient balance")

    user = db.query(User).filter(User.id == user_id).first()
    logger.info("Deduct successful: user_id=%s new_balance=%s", user_id, user.balance)
    return {"user_id": user.id, "balance": user.balance}


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Получить пользователя по ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
