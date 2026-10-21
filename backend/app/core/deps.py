import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_incr
from app.core.security import decode_token
from app.db.models import Airport, AirportAdmin, User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def _user_from_creds(creds: HTTPAuthorizationCredentials | None, db: Session) -> tuple[User, dict]:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None
    user = db.get(User, uuid.UUID(claims["sub"]))
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user, claims


class AuthContext:
    def __init__(self, user: User, claims: dict):
        self.user = user
        self.mfa = bool(claims.get("mfa"))


def get_auth(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    return AuthContext(*_user_from_creds(creds, db))


def get_current_user(ctx: AuthContext = Depends(get_auth)) -> User:
    return ctx.user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User | None:
    if not creds:
        return None
    return _user_from_creds(creds, db)[0]


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if "super_admin" not in user.role_names:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin only")
    return user


def get_airport_or_404(db: Session, airport_id: uuid.UUID) -> Airport:
    airport = db.get(Airport, airport_id)
    if not airport:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Airport not found")
    return airport


def require_airport_admin(
    airport_id: uuid.UUID, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> User:
    """Tenant guard for portal routes: admin must belong to airport_id and have completed 2FA."""
    user = ctx.user
    if "super_admin" in user.role_names:
        return user
    if "airport_admin" not in user.role_names:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Airport admin only")
    member = db.scalar(
        select(AirportAdmin).where(AirportAdmin.user_id == user.id, AirportAdmin.airport_id == airport_id)
    )
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not an admin of this airport")
    if not ctx.mfa:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "2FA required")
    return user


def rate_limit(name: str, limit: int, window: int = 60):
    def dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        n = cache_incr(f"rl:{name}:{ip}", window)
        if n and n > limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")

    return dep


def user_rate_limit(name: str, key: str, limit: int, window: int = 60) -> None:
    n = cache_incr(f"rl:{name}:{key}", window)
    if n and n > limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
