"""Billing Service configuration."""

import os


DATABASE_URL = os.getenv("DATABASE_URL")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_AVAILABLE = os.getenv("RABBITMQ_AVAILABLE")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS").split(",")
    if origin.strip()
]
APP_VERSION = os.getenv("APP_VERSION")
