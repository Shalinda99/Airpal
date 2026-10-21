from celery import Celery

from app.core.config import settings

celery_app = Celery("airpal", broker=settings.redis_url or "memory://", backend=None, include=["app.workers.tasks"])
celery_app.conf.update(
    task_ignore_result=True,
    timezone="UTC",
    beat_schedule={
        "refresh-flight-boards": {"task": "app.workers.tasks.refresh_boards", "schedule": 60.0},
        "ticket-changes": {"task": "app.workers.tasks.ticket_changes", "schedule": 120.0},
        "send-notifications": {"task": "app.workers.tasks.send_notifications", "schedule": 30.0},
        "review-reminders": {"task": "app.workers.tasks.review_reminders", "schedule": 86400.0},
        "retention-purge": {"task": "app.workers.tasks.retention_purge", "schedule": 3600.0},
    },
)
