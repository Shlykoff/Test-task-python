"""Notification Service configuration."""

import os


DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_AVAILABLE = os.getenv("RABBITMQ_AVAILABLE")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS").split(",")
    if origin.strip()
]
APP_VERSION = os.getenv("APP_VERSION")

# RS256 public key for local JWT verification
JWT_ALGORITHM = "RS256"
JWT_PUBLIC_KEY_PEM = os.getenv("JWT_PUBLIC_KEY")
if not JWT_PUBLIC_KEY_PEM:
    key_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keys", "jwt_public.pem")
    if os.path.exists(key_file):
        with open(key_file) as f:
            JWT_PUBLIC_KEY_PEM = f.read()
