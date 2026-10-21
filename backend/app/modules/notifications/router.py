from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import DeviceToken, NotificationPref, User
from app.db.session import get_db
from app.modules.notifications import service

router = APIRouter(prefix="/me", tags=["notifications"])


class DeviceIn(BaseModel):
    token: str = Field(min_length=10, max_length=255)
    platform: str = "expo"


class PrefsIn(BaseModel):
    gate_change: bool = True
    delay: bool = True
    boarding: bool = True
    ride_reminder: bool = True


class ReminderIn(BaseModel):
    title: str = Field(max_length=200)
    body: str = Field(max_length=500)
    when: datetime
    key: str | None = Field(None, max_length=80)


@router.post("/devices", status_code=201)
def register_device(body: DeviceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(DeviceToken).where(DeviceToken.token == body.token))
    if row:
        row.user_id = user.id
    else:
        db.add(DeviceToken(user_id=user.id, token=body.token, platform=body.platform))
    db.commit()
    return {"ok": True}


@router.get("/notification-prefs")
def get_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(NotificationPref, user.id) or NotificationPref(user_id=user.id)
    return {k: bool(getattr(p, k, True)) for k in ("gate_change", "delay", "boarding", "ride_reminder")}


@router.put("/notification-prefs")
def put_prefs(body: PrefsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(NotificationPref, user.id)
    if not p:
        p = NotificationPref(user_id=user.id)
        db.add(p)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return body


@router.post("/reminders", status_code=201)
def create_reminder(body: ReminderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ride reminder ('book your ride at ...'), delivered by the worker at `when`."""
    n = service.schedule(db, user.id, "ride_reminder", body.title, body.body, body.when,
                         dedupe_key=body.key and f"reminder:{body.key}")
    return {"scheduled": bool(n), "id": str(n.id) if n else None}
