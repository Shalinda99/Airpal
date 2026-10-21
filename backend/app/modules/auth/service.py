import logging
import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.config import settings
from app.core.security import (
    create_access_token,
    new_opaque_token,
    sha256,
    verify_password,
    verify_totp,
)
from app.db.base import utcnow
from app.db.models import (
    AgentConversation,
    AgentMessage,
    Consent,
    DeviceToken,
    Feedback,
    Notification,
    NotificationPref,
    RefreshToken,
    SavedPlace,
    Ticket,
    User,
    UserRole,
)

log = logging.getLogger(__name__)


def issue_tokens(db: Session, user: User, mfa: bool) -> dict:
    refresh = new_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=sha256(refresh),
            mfa=mfa,
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role_names, mfa),
        "refresh_token": refresh,
        "token_type": "bearer",
        "mfa_required_setup": ("airport_admin" in user.role_names) and not user.totp_enabled,
    }


def authenticate(db: Session, email: str, password: str, otp: str | None) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active or user.deleted_at or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    mfa = False
    if user.totp_enabled:
        if not otp:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "otp_required")
        secret = crypto.decrypt(user.totp_secret_enc)
        if not secret or not verify_totp(secret, otp):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid one-time code")
        mfa = True
    return user, mfa


def rotate_refresh(db: Session, token: str) -> dict:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(token)))
    if not row or row.revoked_at or row.expires_at < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = db.get(User, row.user_id)
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    row.revoked_at = utcnow()
    return issue_tokens(db, user, mfa=row.mfa)


def revoke_refresh(db: Session, token: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(token)))
    if row and not row.revoked_at:
        row.revoked_at = utcnow()
        db.commit()


def create_user(db: Session, email: str | None, password: str | None, role: str, **kw) -> User:
    from app.core.security import hash_password

    user = User(
        email=email.lower() if email else None,
        password_hash=hash_password(password) if password else None,
        **kw,
    )
    user.roles.append(UserRole(role=role))
    db.add(user)
    db.flush()
    db.add(NotificationPref(user_id=user.id))
    return user


def delete_user_data(db: Session, user: User) -> None:
    """GDPR-style erasure: remove personal data, anonymise the account."""
    uid = user.id
    conv_ids = select(AgentConversation.id).where(AgentConversation.user_id == uid)
    msg_ids = select(AgentMessage.id).where(AgentMessage.conversation_id.in_(conv_ids))
    db.execute(delete(Feedback).where(Feedback.message_id.in_(msg_ids)))
    db.execute(delete(AgentMessage).where(AgentMessage.conversation_id.in_(conv_ids)))
    db.execute(delete(AgentConversation).where(AgentConversation.user_id == uid))
    for model in (Ticket, SavedPlace, DeviceToken, Notification, Consent, NotificationPref, RefreshToken):
        db.execute(delete(model).where(model.user_id == uid))
    user.email = f"deleted-{uuid.uuid4().hex}@deleted.invalid"
    user.password_hash = None
    user.totp_secret_enc = None
    user.totp_enabled = False
    user.is_active = False
    user.deleted_at = utcnow()
    db.commit()
