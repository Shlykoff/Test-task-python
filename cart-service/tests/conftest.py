import os

os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
os.environ.setdefault("CART_TTL", "604800")
os.environ.setdefault("PRODUCT_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("APP_VERSION", "test")
