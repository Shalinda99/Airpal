import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import sha256
from app.db.models import AnalyticsEvent, Consent, User


def has_consent(db: Session, user: User | None) -> bool:
    if not user:
        return False
    c = db.scalar(select(Consent).where(Consent.user_id == user.id, Consent.type == "analytics"))
    return bool(c and c.granted)


def record_event(db: Session, airport_id: uuid.UUID | None, event_type: str, props: dict | None,
                 user: User | None, require_consent: bool = True) -> bool:
    """Anonymised event. Session hash rotates daily and cannot be mapped back to a user without the secret."""
    if require_consent and not has_consent(db, user):
        return False
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    sess = sha256(f"{user.id}:{day}:{settings.jwt_secret}") if user else None
    db.add(AnalyticsEvent(airport_id=airport_id, event_type=event_type, props=props or {}, session_hash=sess))
    db.commit()
    return True
