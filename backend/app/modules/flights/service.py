import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get_json, cache_set_json
from app.core.config import settings
from app.db.models import Airport, FlightCache
from app.integrations.flights import get_flight_provider
from app.integrations.flights.base import ProviderError

log = logging.getLogger(__name__)


def _window(hours_back: int = 2, hours_ahead: int = 10) -> tuple[datetime, datetime]:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    start = now.replace(minute=(now.minute // 15) * 15) - timedelta(hours=hours_back)
    return start, start + timedelta(hours=hours_back + hours_ahead)


def get_board(db: Session, airport: Airport, force_refresh: bool = False) -> dict:
    """Cached board for an airport. Falls back to last stored copy when the provider fails."""
    if not airport.iata:
        return {"flights": [], "stale": False, "provider": None, "fetched_at": None}
    key = f"board:{airport.id}"
    if not force_refresh:
        hit = cache_get_json(key)
        if hit:
            return hit
    start, end = _window()
    provider = get_flight_provider()
    try:
        flights = [f.to_dict() for f in provider.get_board(airport.iata, airport.tz, start, end)]
        result = {
            "flights": flights,
            "stale": False,
            "provider": provider.name,
            "fetched_at": datetime.now(UTC).isoformat(),
        }
        cache_set_json(key, result, settings.flights_cache_ttl)
        row = db.scalar(select(FlightCache).where(FlightCache.airport_id == airport.id,
                                                  FlightCache.flight_key == "board"))
        if row:
            row.payload = result
            row.fetched_at = datetime.now(UTC)
        else:
            db.add(FlightCache(airport_id=airport.id, flight_key="board", payload=result))
        db.commit()
        return result
    except ProviderError as e:
        log.warning("flight provider failed for %s: %s", airport.iata, e)
        row = db.scalar(select(FlightCache).where(FlightCache.airport_id == airport.id,
                                                  FlightCache.flight_key == "board"))
        if row:
            return {**row.payload, "stale": True}
        return {"flights": [], "stale": True, "provider": provider.name, "fetched_at": None,
                "error": "provider_unavailable"}


def filter_board(board: dict, direction: str | None, status: str | None, airline: str | None, q: str | None):
    items = board["flights"]
    if direction:
        items = [f for f in items if f["direction"] == direction]
    if status:
        items = [f for f in items if f["status"] == status]
    if airline:
        items = [f for f in items if (f.get("airline") or "").lower().startswith(airline.lower())]
    if q:
        ql = q.lower()
        items = [f for f in items if ql in f["flight_number"].lower() or ql in (f.get("other_airport_name") or "").lower()
                 or ql == (f.get("other_airport_iata") or "").lower()]
    return sorted(items, key=lambda f: f["scheduled"] or "")


def get_flight_status(flight_number: str, date: str) -> list[dict]:
    key = f"flight:{flight_number.upper()}:{date}"
    hit = cache_get_json(key)
    if hit is not None:
        return hit
    try:
        legs = [f.to_dict() for f in get_flight_provider().get_flight(flight_number, date)]
    except ProviderError as e:
        log.warning("flight lookup failed: %s", e)
        return []
    cache_set_json(key, legs, settings.flights_cache_ttl)
    return legs
