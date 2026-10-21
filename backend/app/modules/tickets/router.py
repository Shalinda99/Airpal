import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.models import Airport, Ticket, User
from app.db.session import get_db
from app.modules.flights.service import get_flight_status
from app.modules.journey.gates import gate_walk_minutes
from app.modules.tickets.bcbp import BCBPError, decode_bcbp

router = APIRouter(prefix="/tickets", tags=["tickets"])


class DecodeIn(BaseModel):
    raw: str = Field(min_length=20, max_length=600)


class TicketIn(BaseModel):
    flight_number: str | None = Field(None, pattern=r"^[A-Za-z0-9]{2}\d{1,4}[A-Za-z]?$")
    flight_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    raw_bcbp: str | None = Field(None, max_length=600)
    pnr: str | None = Field(None, max_length=10)
    passenger_name: str | None = Field(None, max_length=60)
    seat: str | None = Field(None, max_length=5)
    baggage_allowance: str | None = Field(None, max_length=100)
    origin: str | None = Field(None, min_length=3, max_length=3)
    destination: str | None = Field(None, min_length=3, max_length=3)


@router.post("/decode-bcbp")
def decode(body: DecodeIn, user: User = Depends(get_current_user)):
    try:
        return decode_bcbp(body.raw).to_dict()
    except BCBPError as e:
        raise HTTPException(422, str(e)) from None


def refresh_from_flight(db: Session, t: Ticket) -> None:
    """Fill gate/terminal/boarding time from live flight data (departure leg)."""
    legs = [leg for leg in get_flight_status(t.flight_number, t.flight_date) if leg["direction"] == "departure"]
    if t.origin:
        legs = [leg for leg in legs if leg.get("extra", {}).get("airport_iata") in (None, t.origin)] or legs
    if not legs:
        return
    leg = legs[0]
    t.gate = leg.get("gate") or t.gate
    t.terminal = leg.get("terminal") or t.terminal
    when = leg.get("estimated") or leg.get("scheduled")
    if when:
        dep = datetime.fromisoformat(when)
        t.boarding_time = dep - timedelta(minutes=40)
    t.destination = t.destination or leg.get("other_airport_iata")
    t.last_status = {"status": leg["status"], "scheduled": leg.get("scheduled"), "estimated": leg.get("estimated"),
                     "gate": t.gate, "terminal": t.terminal, "refreshed_at": datetime.now(UTC).isoformat()}
    if t.origin and not t.airport_id:
        ap = db.scalar(select(Airport).where(Airport.iata == t.origin))
        t.airport_id = ap.id if ap else None


def serialize(db: Session, t: Ticket) -> dict:
    walk = None
    leave_for_gate = None
    if t.airport_id and t.gate:
        ap = db.get(Airport, t.airport_id)
        walk = gate_walk_minutes(db, ap, t.gate) if ap else None
        if walk is not None and t.boarding_time:
            leave_for_gate = (t.boarding_time - timedelta(minutes=walk)).isoformat()
    return {
        "id": str(t.id), "flight_number": t.flight_number, "flight_date": t.flight_date, "origin": t.origin,
        "destination": t.destination, "airport_id": str(t.airport_id) if t.airport_id else None,
        "passenger_name": crypto.decrypt(t.passenger_name_enc), "pnr": crypto.decrypt(t.pnr_enc),
        "seat": t.seat, "gate": t.gate, "terminal": t.terminal,
        "boarding_time": t.boarding_time.isoformat() if t.boarding_time else None,
        "baggage_allowance": t.baggage_allowance, "source": t.source, "status": t.last_status,
        "gate_walk_minutes": walk, "leave_for_gate_at": leave_for_gate,
    }


@router.post("", status_code=201)
def create(body: TicketIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    source = "manual"
    if body.raw_bcbp:
        try:
            bp = decode_bcbp(body.raw_bcbp)
        except BCBPError as e:
            raise HTTPException(422, str(e)) from None
        data |= {"flight_number": bp.flight_number, "flight_date": bp.flight_date, "pnr": bp.pnr,
                 "passenger_name": bp.passenger_name, "seat": data.get("seat") or bp.seat, "origin": bp.origin,
                 "destination": bp.destination}
        source = "scan"
    if not data.get("flight_number") or not data.get("flight_date"):
        raise HTTPException(422, "flight_number and flight_date are required")
    fn = data["flight_number"].upper()
    count = len(db.scalars(select(Ticket.id).where(Ticket.user_id == user.id)).all())
    if count >= 20:
        raise HTTPException(409, "Ticket limit reached")
    flight_day = datetime.fromisoformat(data["flight_date"] + "T00:00:00+00:00")
    t = Ticket(
        user_id=user.id, flight_number=fn, flight_date=data["flight_date"],
        origin=(data.get("origin") or "").upper() or None, destination=(data.get("destination") or "").upper() or None,
        pnr_enc=crypto.encrypt(data.get("pnr")), pnr_bidx=crypto.blind_index(data["pnr"]) if data.get("pnr") else None,
        passenger_name_enc=crypto.encrypt(data.get("passenger_name")),
        raw_bcbp_enc=crypto.encrypt(body.raw_bcbp) if body.raw_bcbp else None,
        seat=data.get("seat"), baggage_allowance=data.get("baggage_allowance"), source=source,
        expires_at=flight_day + timedelta(days=1 + settings.ticket_retention_days),
    )
    refresh_from_flight(db, t)
    db.add(t)
    db.commit()
    return serialize(db, t)


@router.get("")
def list_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.flight_date))
    return [serialize(db, t) for t in rows]


def _own(db: Session, user: User, ticket_id: uuid.UUID) -> Ticket:
    t = db.scalar(select(Ticket).where(Ticket.id == ticket_id, Ticket.user_id == user.id))
    if not t:
        raise HTTPException(404, "Ticket not found")
    return t


@router.get("/{ticket_id}")
def get_ticket(ticket_id: uuid.UUID, refresh: bool = True, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    t = _own(db, user, ticket_id)
    if refresh:
        refresh_from_flight(db, t)
        db.commit()
    return serialize(db, t)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _own(db, user, ticket_id)
    db.delete(t)
    db.commit()

