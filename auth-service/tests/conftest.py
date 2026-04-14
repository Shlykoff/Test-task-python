import os
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Generate RSA key pair for tests
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

PRIVATE_KEY_PEM = _private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()
).decode()

PUBLIC_KEY_PEM = _public_key.public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

os.environ.setdefault("JWT_PRIVATE_KEY", PRIVATE_KEY_PEM)
os.environ.setdefault("JWT_PUBLIC_KEY", PUBLIC_KEY_PEM)
os.environ.setdefault("USER_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("APP_VERSION", "test")

# Export keys for other test files
pytest.JWT_PRIVATE_KEY = PRIVATE_KEY_PEM
pytest.JWT_PUBLIC_KEY = PUBLIC_KEY_PEM
