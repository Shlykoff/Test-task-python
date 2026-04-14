"""Order Service configuration."""

import os

SAGA_TIMEOUT_SECONDS = int(os.getenv("SAGA_TIMEOUT", "300"))

# --- Config: RS256 JWT (asymmetric verification) ---
JWT_ALGORITHM = "RS256"

JWT_PUBLIC_KEY_PEM = os.getenv("JWT_PUBLIC_KEY")
if not JWT_PUBLIC_KEY_PEM:
    key_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keys", "jwt_public.pem")
    if os.path.exists(key_file):
        with open(key_file) as f:
            JWT_PUBLIC_KEY_PEM = f.read()

DATABASE_URL = os.getenv("DATABASE_URL")
CART_SERVICE_URL = os.getenv("CART_SERVICE_URL")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
RABBITMQ_AVAILABLE = os.getenv("RABBITMQ_AVAILABLE")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS").split(",")
    if origin.strip()
]
APP_VERSION = os.getenv("APP_VERSION")
