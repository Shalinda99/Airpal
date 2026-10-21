import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_airport_or_404, rate_limit
from app.db.session import get_db
from app.modules.flights import service

router = APIRouter(tags=["flights"], dependencies=[Depends(rate_limit("flights", 120))])


@router.get("/airports/{airport_id}/flights")
def list_flights(
    airport_id: uuid.UUID,
    direction: Literal["departure", "arrival"] | None = None,
    status: str | None = None,
    airline: str | None = None,
    q: str | None = Query(None, max_length=60),
    db: Session = Depends(get_db),
):
    airport = get_airport_or_404(db, airport_id)
    board = service.get_board(db, airport)
    return {
        "airport_id": str(airport.id),
        "provider": board.get("provider"),
        "fetched_at": board.get("fetched_at"),
        "stale": board.get("stale", False),
        "flights": service.filter_board(board, direction, status, airline, q),
    }


@router.get("/flights/{flight_number}")
def flight_status(flight_number: str, date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")):
    if not re.fullmatch(r"[A-Za-z0-9]{2}\d{1,4}[A-Za-z]?", flight_number):
        raise HTTPException(422, "Invalid flight number")
    return {"flight_number": flight_number.upper(), "date": date, "legs": service.get_flight_status(flight_number, date)}
