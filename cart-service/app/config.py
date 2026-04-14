"""Cart Service configuration."""

import os


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
CART_TTL_SECONDS = int(os.getenv("CART_TTL", "604800"))
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost").split(",")
    if origin.strip()
]
APP_VERSION = os.getenv("APP_VERSION")
