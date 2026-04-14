"""Product routes."""

import logging

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.dependencies import get_db
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockReserveRequest,
    StockReserveResponse,
)
from app.services.product import to_response

logger = logging.getLogger("product-service")

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products", response_model=list[ProductResponse])
async def list_products(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Список товаров. Пагинация: skip/limit."""
    products = db.query(Product).offset(skip).limit(min(limit, 100)).all()
    return [to_response(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Детальная информация о товаре."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return to_response(product)


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    """Создать товар (админ)."""
    product = Product(
        name=body.name,
        description=body.description,
        cost_price=body.cost_price,
        quantity=body.quantity,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return to_response(product)


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    """Обновить товар (админ)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return to_response(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Удалить товар (админ)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()


@router.post("/products/reserve-stock", response_model=StockReserveResponse)
async def reserve_stock(body: StockReserveRequest, db: Session = Depends(get_db)):
    """Зарезервировать товар. Атомарная операция — защита от race condition."""
    logger.info("Reserve stock: product_id=%s quantity=%s", body.product_id, body.quantity)
    result = db.execute(
        update(Product)
        .where(Product.id == body.product_id, Product.quantity >= body.quantity)
        .values(quantity=Product.quantity - body.quantity)
    )
    db.commit()

    if result.rowcount == 0:
        product = db.query(Product).filter(Product.id == body.product_id).first()
        if not product:
            logger.warning("Reserve stock failed: product_id=%s not found", body.product_id)
            raise HTTPException(status_code=404, detail="Product not found")
        logger.warning(
            "Reserve stock failed: product_id=%s insufficient quantity (available=%s requested=%s)",
            body.product_id, product.quantity, body.quantity,
        )
        return StockReserveResponse(
            success=False,
            product_id=body.product_id,
            remaining_quantity=product.quantity,
        )

    product = db.query(Product).filter(Product.id == body.product_id).first()
    logger.info("Reserve stock successful: product_id=%s remaining=%s", body.product_id, product.quantity)
    return StockReserveResponse(
        success=True,
        product_id=body.product_id,
        remaining_quantity=product.quantity,
    )


@router.post("/products/unreserve-stock", response_model=StockReserveResponse)
async def unreserve_stock(body: StockReserveRequest, db: Session = Depends(get_db)):
    """Вернуть зарезервированный товар (при отмене заказа)."""
    result = db.execute(
        update(Product)
        .where(Product.id == body.product_id)
        .values(quantity=Product.quantity + body.quantity)
    )
    db.commit()

    if result.rowcount == 0:
        product = db.query(Product).filter(Product.id == body.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

    product = db.query(Product).filter(Product.id == body.product_id).first()
    return StockReserveResponse(
        success=True,
        product_id=body.product_id,
        remaining_quantity=product.quantity,
    )
