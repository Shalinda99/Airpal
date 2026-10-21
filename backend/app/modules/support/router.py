import re
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_airport_or_404
from app.db.models import Airport, EmergencyContact, SupportChannel
from app.db.session import get_db

router = APIRouter(prefix="/airports/{airport_id}", tags=["support"])


def is_open(hours: dict | None, tz: str, now: datetime | None = None) -> bool:
    """hours: {"days": [0-6, Monday=0], "open": "HH:MM", "close": "HH:MM"}; None = always open."""
    if not hours:
        return True
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo(tz))
    if local.weekday() not in hours.get("days", list(range(7))):
        return False
    hhmm = local.strftime("%H:%M")
    o, c = hours.get("open", "00:00"), hours.get("close", "23:59")
    return o <= hhmm < c if o <= c else (hhmm >= o or hhmm < c)


def link_for(ch: SupportChannel) -> str:
    if ch.type == "phone":
        return "tel:" + re.sub(r"[^\d+]", "", ch.value)
    if ch.type == "whatsapp":
        return "https://wa.me/" + re.sub(r"\D", "", ch.value)
    return f"mailto:{ch.value}"


def support_options(db: Session, airport: Airport, now: datetime | None = None) -> list[dict]:
    rows = db.scalars(select(SupportChannel).where(SupportChannel.airport_id == airport.id)
                      .order_by(SupportChannel.created_at))
    out = []
    for ch in rows:
        open_now = is_open(ch.hours, airport.tz, now)
        out.append({
            "id": str(ch.id), "type": ch.type, "value": ch.value, "link": link_for(ch), "hours": ch.hours,
            "open_now": open_now,
            "out_of_hours_message": None if open_now else (ch.out_of_hours_message or
                                                           "Currently closed. Please try again during opening hours."),
        })
    return out


@router.get("/support")
def support(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    return {"channels": support_options(db, get_airport_or_404(db, airport_id))}


@router.get("/emergency-contacts")
def emergency(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    get_airport_or_404(db, airport_id)
    rows = db.scalars(select(EmergencyContact).where(EmergencyContact.airport_id == airport_id))
    return [{"label": r.label, "phone": r.phone} for r in rows]
