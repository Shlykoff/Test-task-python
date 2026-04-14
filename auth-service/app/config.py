"""Auth Service configuration."""

import os


JWT_ALGORITHM = "RS256"


def _load_jwt_key(env_var: str, filename: str) -> str:
    """Load JWT key from env var or file."""
    value = os.getenv(env_var)
    if value:
        return value
    key_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keys", filename)
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read()
    raise RuntimeError(f"{env_var} env var or keys/{filename} file is required for RS256.")


JWT_PRIVATE_KEY_PEM = _load_jwt_key("JWT_PRIVATE_KEY", "jwt_private.pem")
JWT_PUBLIC_KEY_PEM = _load_jwt_key("JWT_PUBLIC_KEY", "jwt_public.pem")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE"))
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS").split(",")
    if origin.strip()
]
APP_VERSION = os.getenv("APP_VERSION")
