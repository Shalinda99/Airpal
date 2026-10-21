import uuid
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.audit import audit
from app.core import crypto
from app.core.config import settings
from app.core.deps import AuthContext, get_auth, get_current_user, rate_limit
from app.core.security import (
    create_purpose_token,
    decode_token,
    new_totp_secret,
    sha256,
    totp_uri,
    verify_totp,
)
from app.db.base import utcnow
from app.db.models import AirportAdmin, Consent, Invitation, User, UserRole
from app.db.session import get_db
from app.modules.auth import service

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    locale: str = "en"


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class OtpIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class AcceptIn(BaseModel):
    password: str = Field(min_length=10, max_length=128)


class VerifyIn(BaseModel):
    token: str


class ConsentIn(BaseModel):
    type: str = "analytics"
    granted: bool


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit("register", 10))])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = service.create_user(db, body.email, body.password, "passenger", locale=body.locale)
    db.commit()
    token = create_purpose_token(user.id, "verify_email")
    out = service.issue_tokens(db, user, mfa=False)
    # Email delivery is an extension point (SMTP/provider); dev returns the token directly.
    if not settings.is_prod:
        out["dev_verify_token"] = token
    return out


@router.post("/guest", status_code=201, dependencies=[Depends(rate_limit("guest", 30))])
def guest(db: Session = Depends(get_db)):
    user = service.create_user(db, None, None, "passenger", is_guest=True)
    db.commit()
    return service.issue_tokens(db, user, mfa=False)


@router.post("/login", dependencies=[Depends(rate_limit("login", 10))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user, mfa = service.authenticate(db, body.email, body.password, body.otp)
    return service.issue_tokens(db, user, mfa)


@router.post("/refresh", dependencies=[Depends(rate_limit("refresh", 60))])
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    return service.rotate_refresh(db, body.refresh_token)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    service.revoke_refresh(db, body.refresh_token)


@router.post("/verify-email")
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    try:
        claims = decode_token(body.token, "verify_email")
    except jwt.PyJWTError:
        raise HTTPException(400, "Invalid or expired token") from None
    user = db.get(User, uuid.UUID(claims["sub"]))
    if not user:
        raise HTTPException(404, "User not found")
    user.email_verified_at = utcnow()
    db.commit()
    return {"verified": True}


@router.post("/2fa/setup")
def setup_2fa(ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    user = ctx.user
    if "airport_admin" not in user.role_names and "super_admin" not in user.role_names:
        raise HTTPException(403, "Only admins can enable 2FA")
    if user.totp_enabled:
        raise HTTPException(409, "2FA already enabled")
    secret = new_totp_secret()
    user.totp_secret_enc = crypto.encrypt(secret)
    db.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, user.email or "admin")}


@router.post("/2fa/verify")
def verify_2fa(body: OtpIn, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    user = ctx.user
    secret = crypto.decrypt(user.totp_secret_enc)
    if not secret or not verify_totp(secret, body.code):
        raise HTTPException(400, "Invalid code")
    user.totp_enabled = True
    audit(db, user.id, "2fa.enable", "user", user.id)
    db.commit()
    return service.issue_tokens(db, user, mfa=True)


@router.post("/invitations/{token}/accept", status_code=201)
def accept_invitation(token: str, body: AcceptIn, request: Request, db: Session = Depends(get_db)):
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == sha256(token)))
    if not inv or inv.accepted_at or inv.expires_at < datetime.now(UTC):
        raise HTTPException(400, "Invitation invalid or expired")
    user = db.scalar(select(User).where(User.email == inv.email.lower()))
    if user:
        if "airport_admin" not in user.role_names:
            user.roles.append(UserRole(role="airport_admin"))
    else:
        user = service.create_user(db, inv.email, body.password, "airport_admin")
        user.roles.append(UserRole(role="passenger"))
    # the invite was delivered to this address, so accepting it proves email ownership
    user.email_verified_at = user.email_verified_at or utcnow()
    db.flush()
    db.add(AirportAdmin(user_id=user.id, airport_id=inv.airport_id))
    inv.accepted_at = utcnow()
    audit(db, user.id, "invitation.accept", "airport", inv.airport_id, inv.airport_id,
          ip=request.client.host if request.client else None)
    db.commit()
    return service.issue_tokens(db, user, mfa=False)


# ---------- /me ----------
@me_router.get("")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    admin_airports = [
        str(a) for a in db.scalars(select(AirportAdmin.airport_id).where(AirportAdmin.user_id == user.id))
    ]
    return {
        "id": str(user.id),
        "email": user.email,
        "is_guest": user.is_guest,
        "roles": user.role_names,
        "locale": user.locale,
        "email_verified": bool(user.email_verified_at),
        "totp_enabled": user.totp_enabled,
        "admin_airports": admin_airports,
    }


@me_router.patch("")
def update_me(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if isinstance(body.get("locale"), str) and len(body["locale"]) <= 10:
        user.locale = body["locale"]
        db.commit()
    return {"locale": user.locale}


@me_router.delete("", status_code=204)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.delete_user_data(db, user)


@me_router.get("/consents")
def get_consents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Consent).where(Consent.user_id == user.id)).all()
    return {c.type: c.granted for c in rows}


@me_router.put("/consents")
def put_consent(body: ConsentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Consent).where(Consent.user_id == user.id, Consent.type == body.type))
    if row:
        row.granted = body.granted
    else:
        db.add(Consent(user_id=user.id, type=body.type, granted=body.granted))
    db.commit()
    return {body.type: body.granted}
