import logging
from datetime import timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.base import utcnow
from app.db.models import AgentMessage, Airport, AnalyticsEvent, Ticket
from app.db.session import SessionLocal
from app.modules.flights.service import get_board
from app.modules.notifications import service as notif
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task
def refresh_boards() -> int:
    """Background refresh for verified airports, so passenger requests hit the cache."""
    n = 0
    with SessionLocal() as db:
        for ap in db.scalars(select(Airport).where(Airport.status == "verified")):
            get_board(db, ap, force_refresh=True)
            n += 1
    return n


@celery_app.task
def ticket_changes() -> int:
    with SessionLocal() as db:
        return notif.check_ticket_changes(db)


@celery_app.task
def send_notifications() -> int:
    with SessionLocal() as db:
        return notif.send_due(db)


@celery_app.task
def review_reminders() -> int:
    """Flag airports whose content has not been verified for REVIEW_REMINDER_DAYS (email delivery = extension point)."""
    cutoff = utcnow() - timedelta(days=settings.review_reminder_days)
    n = 0
    with SessionLocal() as db:
        for ap in db.scalars(select(Airport).where(Airport.status == "verified", Airport.last_verified_at < cutoff)):
            if ap.last_review_reminder_at and ap.last_review_reminder_at > cutoff:
                continue
            log.info("Review reminder due for airport %s", ap.iata)
            ap.last_review_reminder_at = utcnow()
            n += 1
        db.commit()
    return n


@celery_app.task
def retention_purge() -> int:
    """Minimal retention: delete expired tickets, old agent messages (90d) and analytics events (180d)."""
    now = utcnow()
    with SessionLocal() as db:
        r1 = db.execute(delete(Ticket).where(Ticket.expires_at < now))
        db.execute(delete(AgentMessage).where(AgentMessage.created_at < now - timedelta(days=90)))
        db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.created_at < now - timedelta(days=180)))
        db.commit()
        return r1.rowcount or 0
