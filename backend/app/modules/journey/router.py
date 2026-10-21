import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_airport_or_404
from app.db.models import JourneyStep
from app.db.session import get_db

router = APIRouter(prefix="/airports/{airport_id}", tags=["journey"])


def serialize_step(s: JourneyStep) -> dict:
    return {
        "id": str(s.id), "flow": s.flow, "scope": s.scope, "order": s.order, "title": s.title,
        "instructions": s.instructions, "documents": s.documents or [], "typical_minutes": s.typical_minutes,
        "tips": s.tips or [], "prohibited_items": s.prohibited_items or [],
    }


@router.get("/journey")
def journey(
    airport_id: uuid.UUID,
    flow: Literal["departure", "arrival", "transit"] = "departure",
    scope: Literal["domestic", "international"] = "international",
    db: Session = Depends(get_db),
):
    airport = get_airport_or_404(db, airport_id)
    if airport.status != "verified":
        return {"basic": True, "version": 0, "steps": []}
    rows = db.scalars(
        select(JourneyStep)
        .where(JourneyStep.airport_id == airport_id, JourneyStep.version_no == airport.current_published_version,
               JourneyStep.flow == flow, JourneyStep.scope.in_([scope, "both"]))
        .order_by(JourneyStep.order)
    )
    return {"basic": False, "version": airport.current_published_version, "flow": flow, "scope": scope,
            "last_verified_at": airport.last_verified_at.isoformat() if airport.last_verified_at else None,
            "steps": [serialize_step(s) for s in rows]}
