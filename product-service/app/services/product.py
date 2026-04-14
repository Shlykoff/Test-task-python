"""Product service business logic."""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.models.product import Product

logger = logging.getLogger("product-service")

SEED_PRODUCTS = [
    {"name": "MacBook Pro 14\"", "description": "Apple M3 Pro, 18GB RAM, 512GB SSD", "cost_price": Decimal("1500.00"), "quantity": 10},
    {"name": "iPhone 15 Pro", "description": "256GB, Natural Titanium", "cost_price": Decimal("800.00"), "quantity": 25},
    {"name": "AirPods Pro 2", "description": "Active Noise Cancellation, USB-C", "cost_price": Decimal("150.00"), "quantity": 50},
    {"name": "iPad Air", "description": "M2 chip, 11-inch, 128GB, Wi-Fi", "cost_price": Decimal("450.00"), "quantity": 15},
    {"name": "Apple Watch Series 9", "description": "45mm, GPS + Cellular", "cost_price": Decimal("300.00"), "quantity": 20},
    {"name": "Sony WH-1000XM5", "description": "Wireless Noise Cancelling Headphones", "cost_price": Decimal("250.00"), "quantity": 30},
    {"name": "Samsung Galaxy S24 Ultra", "description": "256GB, Titanium Gray", "cost_price": Decimal("900.00"), "quantity": 12},
    {"name": "Dell XPS 15", "description": "Intel i7, 16GB RAM, 512GB SSD", "cost_price": Decimal("1100.00"), "quantity": 8},
    {"name": "Logitech MX Master 3S", "description": "Wireless Mouse, Graphite", "cost_price": Decimal("65.00"), "quantity": 100},
    {"name": "Keychron K2", "description": "Mechanical Keyboard, Gateron Brown", "cost_price": Decimal("55.00"), "quantity": 40},
    {"name": "Nintendo Switch OLED", "description": "White Joy-Con", "cost_price": Decimal("260.00"), "quantity": 18},
    {"name": "PS5 Slim", "description": "Digital Edition", "cost_price": Decimal("350.00"), "quantity": 5},
    {"name": "Xbox Series X", "description": "1TB, Black", "cost_price": Decimal("380.00"), "quantity": 7},
    {"name": "Bose QuietComfort Earbuds", "description": "Soapstone", "cost_price": Decimal("180.00"), "quantity": 22},
    {"name": "Razer DeathAdder V3", "description": "Ergonomic Gaming Mouse", "cost_price": Decimal("50.00"), "quantity": 60},
]


def seed_data(db: Session):
    if db.query(Product).count() == 0:
        for p in SEED_PRODUCTS:
            db.add(Product(**p))
        db.commit()


def calc_user_price(cost_price: Decimal) -> Decimal:
    return round(cost_price * Decimal("1.2"), 2)


def to_response(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "cost_price": product.cost_price,
        "quantity": product.quantity,
        "user_price": calc_user_price(product.cost_price),
        "created_at": product.created_at,
    }
