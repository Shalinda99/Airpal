import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import DeviceToken, Notification, NotificationPref, Ticket
from app.modules.tickets.router import refresh_from_flight

log = logging.getLogger(__name__)
EXPO_URL = "https://exp.host/--/api/v2/push/send"


def schedule(db: Session, user_id, type_: str, title: str, body: str, when: datetime | None = None,
             payload: dict | None = None, dedupe_key: str | None = None) -> Notification | None:
    if dedupe_key and db.scalar(select(Notification.id).where(Notification.user_id == user_id,
                                                              Notification.dedupe_key == dedupe_key)):
        return None
    n = Notification(user_id=user_id, type=type_, title=title, body=body, payload=payload,
                     scheduled_for=when or utcnow(), dedupe_key=dedupe_key)
    db.add(n)
    db.commit()
    return n


def _allowed(db: Session, user_id, type_: str) -> bool:
    p = db.get(NotificationPref, user_id)
    return True if not p else bool(getattr(p, type_, True))


def send_due(db: Session) -> int:
    """Send scheduled notifications that are due. Returns count sent."""
    due = list(db.scalars(select(Notification).where(Notification.sent_at.is_(None),
                                                    Notification.scheduled_for <= utcnow()).limit(200)))
    sent = 0
    for n in due:
        if not _allowed(db, n.user_id, n.type):
            n.sent_at = utcnow()
            continue
        tokens = [t.token for t in db.scalars(select(DeviceToken).where(DeviceToken.user_id == n.user_id))]
        if tokens:
            try:
                httpx.post(EXPO_URL, json=[{"to": t, "title": n.title, "body": n.body, "data": n.payload or {},
                                           "sound": "default"} for t in tokens], timeout=10)
            except httpx.HTTPError:
                log.warning("push send failed; will retry")
                continue
        n.sent_at = utcnow()
        sent += 1
    db.commit()
    return sent


def check_ticket_changes(db: Session) -> int:
    """Detect gate changes, delays and boarding for upcoming tickets and queue notifications."""
    now = datetime.now(UTC)
    day_from = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    day_to = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    created = 0
    for t in db.scalars(select(Ticket).where(Ticket.flight_date >= day_from, Ticket.flight_date <= day_to)):
        old = dict(t.last_status or {})
        refresh_from_flight(db, t)
        new = t.last_status or {}
        if not old:
            continue
        key = f"{t.id}"
        if old.get("gate") and new.get("gate") and old["gate"] != new["gate"]:
            if schedule(db, t.user_id, "gate_change", f"Gate change for {t.flight_number}",
                        f"New gate: {new['gate']}", dedupe_key=f"gate:{key}:{new['gate']}"):
                created += 1
        if new.get("status") == "delayed" and old.get("estimated") != new.get("estimated"):
            if schedule(db, t.user_id, "delay", f"{t.flight_number} delayed",
                        f"New estimated time: {new.get('estimated')}", dedupe_key=f"delay:{key}:{new.get('estimated')}"):
                created += 1
        if new.get("status") == "boarding" and old.get("status") != "boarding":
            if schedule(db, t.user_id, "boarding", f"{t.flight_number} is boarding",
                        f"Gate {new.get('gate') or 'see board'}", dedupe_key=f"boarding:{key}"):
                created += 1
    db.commit()
    return created
