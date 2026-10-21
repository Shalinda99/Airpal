import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _key() -> bytes:
    raw = base64.urlsafe_b64decode(settings.data_encryption_key.encode())
    return hashlib.sha256(raw).digest()


def encrypt(plain: str | None) -> str | None:
    if plain is None:
        return None
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plain.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(token: str | None) -> str | None:
    if token is None:
        return None
    data = base64.urlsafe_b64decode(token.encode())
    return AESGCM(_key()).decrypt(data[:12], data[12:], None).decode()


def blind_index(value: str) -> str:
    return hmac.new(settings.blind_index_key.encode(), value.strip().upper().encode(), hashlib.sha256).hexdigest()
