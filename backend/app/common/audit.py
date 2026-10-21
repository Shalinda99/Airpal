import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: Any = None,
    airport_id: uuid.UUID | None = None,
    before: Any = None,
    after: Any = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            airport_id=airport_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
            ip=ip,
        )
    )
