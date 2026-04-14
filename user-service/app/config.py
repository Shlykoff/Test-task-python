"""User Service configuration."""

import os


DATABASE_URL = os.getenv("DATABASE_URL")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS").split(",")
    if origin.strip()
]
APP_VERSION = os.getenv("APP_VERSION")
