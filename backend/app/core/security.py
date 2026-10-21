import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
import pyotp

from app.core.config import settings

ALGO = "HS256"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: uuid.UUID, roles: list[str], mfa: bool) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "mfa": mfa,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def create_purpose_token(user_id: uuid.UUID, purpose: str, hours: int = 48) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "typ": purpose, "exp": now + timedelta(hours=hours)},
        settings.jwt_secret,
        algorithm=ALGO,
    )


def decode_token(token: str, expected_typ: str = "access") -> dict:
    data = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
    if data.get("typ") != expected_typ:
        raise jwt.InvalidTokenError("wrong token type")
    return data


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Airpal")


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
