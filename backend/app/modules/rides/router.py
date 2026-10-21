import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_airport_or_404, get_current_user, get_optional_user
from app.db.models import Airport, PickupPoint, PublishVersion, RideProvider, SavedPlace, Ticket, User
from app.db.session import get_db
from app.integrations.rides.base import Place
from app.integrations.rides.providers import REGISTRY, build_booking_link
from app.integrations.routing import travel_minutes
from app.modules.analytics.service import record_event
from app.modules.flights.service import get_flight_status
from app.modules.rides import timing

router = APIRouter(tags=["rides"])


def pickup_dict(p: PickupPoint) -> dict:
    return {"id": str(p.id), "terminal": p.terminal, "level": p.level, "zone_name": p.zone_name, "lat": p.lat,
            "lon": p.lon, "walking_instructions": p.walking_instructions, "notes": p.notes, "kind": p.kind}


def ride_options(db: Session, airport: Airport) -> dict:
    """Airport-configured providers, in the airport's own order (never ranked by commission)."""
    providers = db.scalars(select(RideProvider).where(RideProvider.airport_id == airport.id,
                                                     RideProvider.enabled.is_(True))
                           .order_by(RideProvider.display_order, RideProvider.provider_key))
    points = db.scalars(select(PickupPoint).where(PickupPoint.airport_id == airport.id))
    return {
        "airport_id": str(airport.id),
        "providers": [
            {"key": p.provider_key, "label": REGISTRY[p.provider_key].label if p.provider_key in REGISTRY else p.provider_key,
             "config": p.config or {}, "price_estimate_supported": REGISTRY[p.provider_key].supports_estimates
             if p.provider_key in REGISTRY else False}
            for p in providers
        ],
        "pickup_points": [pickup_dict(p) for p in points],
    }


@router.get("/airports/{airport_id}/rides/options")
def options(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    return ride_options(db, get_airport_or_404(db, airport_id))


class PlaceIn(BaseModel):
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    nickname: str | None = Field(None, max_length=150)
    formatted_address: str | None = Field(None, max_length=300)
    current_location: bool = False

    def to_place(self) -> Place:
        return Place(self.lat, self.lon, self.nickname, self.formatted_address, self.current_location)


class LinkIn(BaseModel):
    airport_id: uuid.UUID
    provider: str
    pickup: PlaceIn
    dropoff: PlaceIn
    route_type: Literal["to_airport", "from_airport", "terminal_transfer", "airport_transfer"] = "from_airport"


@router.post("/rides/link")
def link(body: LinkIn, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    airport = get_airport_or_404(db, body.airport_id)
    enabled = db.scalar(select(RideProvider).where(RideProvider.airport_id == airport.id,
                                                   RideProvider.provider_key == body.provider,
                                                   RideProvider.enabled.is_(True)))
    if not enabled:
        raise HTTPException(404, "Provider not available at this airport")
    try:
        result = build_booking_link(body.provider, body.pickup.to_place(), body.dropoff.to_place(),
                                    {"config": enabled.config})
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return result


class IntentIn(BaseModel):
    airport_id: uuid.UUID
    provider: str
    route_type: str


@router.post("/rides/intent", status_code=202)
def intent(body: IntentIn, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    """Anonymised ride-intent event (provider tapped + route type). No ride details stored; needs consent."""
    record_event(db, body.airport_id, "ride_intent", {"provider": body.provider[:32], "route_type": body.route_type[:32]},
                 user)
    return {"ok": True}


class TimingIn(BaseModel):
    airport_id: uuid.UUID
    kind: Literal["to_airport", "from_airport"]
    other: PlaceIn  # origin (to_airport) or destination (from_airport)
    pickup_point_id: uuid.UUID | None = None
    ticket_id: uuid.UUID | None = None
    flight_number: str | None = None
    flight_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    event_time: datetime | None = None  # explicit flight time, or arrive-by when no flight
    scope: Literal["domestic", "international"] = "international"
    has_checked_bag: bool = False
    arrive_by: bool = False

    @model_validator(mode="after")
    def _need_time(self):
        if not (self.ticket_id or self.flight_number or self.event_time):
            raise ValueError("Provide ticket_id, flight_number+flight_date or event_time")
        return self


def _durations(db: Session, airport: Airport) -> dict:
    row = db.scalar(select(PublishVersion).where(PublishVersion.airport_id == airport.id,
                                                 PublishVersion.version_no == airport.current_published_version))
    return row.snapshot if row else {}


@router.post("/rides/timing")
def ride_timing(body: TimingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    airport = get_airport_or_404(db, body.airport_id)
    event: datetime | None = body.event_time
    fnum, fdate = body.flight_number, body.flight_date
    if body.ticket_id:
        t = db.scalar(select(Ticket).where(Ticket.id == body.ticket_id, Ticket.user_id == user.id))
        if not t:
            raise HTTPException(404, "Ticket not found")
        fnum, fdate = t.flight_number, t.flight_date
    source = "event_time"
    if event is None:
        if not (fnum and fdate):
            raise HTTPException(422, "flight_number and flight_date required")
        want = "departure" if body.kind == "to_airport" else "arrival"
        legs = [leg for leg in get_flight_status(fnum, fdate) if leg["direction"] == want
                and (leg.get("extra", {}).get("airport_iata") in (None, airport.iata))]
        if not legs:
            raise HTTPException(404, "Flight time not available; provide event_time")
        leg = legs[0]
        event = datetime.fromisoformat(leg["estimated"] or leg["scheduled"])
        source = "live_flight"
    if event.tzinfo is None:
        event = event.replace(tzinfo=UTC)

    point = None
    if body.pickup_point_id:
        point = db.scalar(select(PickupPoint).where(PickupPoint.id == body.pickup_point_id,
                                                    PickupPoint.airport_id == airport.id))
    elif body.kind == "from_airport":
        point = db.scalar(select(PickupPoint).where(PickupPoint.airport_id == airport.id,
                                                    PickupPoint.kind == "pickup"))
    airport_ll = (point.lat, point.lon) if point else (airport.lat, airport.lon)
    if body.other.lat is None or body.other.lon is None:
        raise HTTPException(422, "other place needs coordinates")
    other_ll = (body.other.lat, body.other.lon)
    origin, dest = (other_ll, airport_ll) if body.kind == "to_airport" else (airport_ll, other_ll)
    minutes, routing_source = travel_minutes(origin, dest)

    durations = _durations(db, airport)
    intl = body.scope == "international"
    if body.kind == "to_airport":
        res = (timing.compute_arrive_by(event, minutes) if body.arrive_by
               else timing.compute_to_airport(event, minutes, durations, intl, body.has_checked_bag))
    else:
        res = timing.compute_from_airport(event, minutes, durations, intl, body.has_checked_bag)
    out = timing.serialize(res)
    out |= {"event_time": event.isoformat(), "event_source": source, "routing_source": routing_source,
            "pickup_point": pickup_dict(point) if point else None}
    return out


# ---------- saved & recent places ----------
class SavedPlaceIn(BaseModel):
    kind: Literal["home", "hotel", "work", "saved", "recent"] = "saved"
    label: str = Field(max_length=100)
    nickname: str = Field(max_length=150)
    formatted_address: str | None = Field(None, max_length=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


def _pl(p: SavedPlace) -> dict:
    return {"id": str(p.id), "kind": p.kind, "label": p.label, "nickname": p.nickname,
            "formatted_address": p.formatted_address, "lat": p.lat, "lon": p.lon}


@router.get("/me/places")
def list_places(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedPlace).where(SavedPlace.user_id == user.id).order_by(SavedPlace.updated_at.desc()))
    return [_pl(p) for p in rows]


@router.post("/me/places", status_code=201)
def add_place(body: SavedPlaceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = SavedPlace(user_id=user.id, **body.model_dump())
    db.add(p)
    if body.kind == "recent":  # keep only the 10 most recent
        old = db.scalars(select(SavedPlace).where(SavedPlace.user_id == user.id, SavedPlace.kind == "recent")
                         .order_by(SavedPlace.updated_at.desc()).offset(9)).all()
        for o in old:
            db.delete(o)
    db.commit()
    return _pl(p)


@router.put("/me/places/{place_id}")
def update_place(place_id: uuid.UUID, body: SavedPlaceIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    p = db.scalar(select(SavedPlace).where(SavedPlace.id == place_id, SavedPlace.user_id == user.id))
    if not p:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return _pl(p)


@router.delete("/me/places/{place_id}", status_code=204)
def delete_place(place_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(SavedPlace).where(SavedPlace.id == place_id, SavedPlace.user_id == user.id))
    if p:
        db.delete(p)
        db.commit()
