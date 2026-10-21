import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.cache import cache_get_json, cache_set_json
from app.core.config import settings
from app.core.deps import get_airport_or_404
from app.db.base import utcnow
from app.db.models import Airport, Notice
from app.db.session import get_db
from app.integrations.weather import fetch_weather

router = APIRouter(prefix="/airports", tags=["airports"])


def serialize(a: Airport) -> dict:
    verified = a.status == "verified"
    return {
        "id": str(a.id),
        "iata": a.iata,
        "icao": a.icao,
        "name": a.name,
        "city": a.city,
        "country": a.country,
        "lat": a.lat,
        "lon": a.lon,
        "tz": a.tz,
        "status": a.status,
        "badge": "Verified by airport" if verified else "Basic Mode (unverified)",
        "verified": verified,
        "last_verified_at": a.last_verified_at.isoformat() if a.last_verified_at else None,
        "content_version": a.current_published_version,
    }


@router.get("")
def search(q: str = Query("", max_length=60), limit: int = Query(20, le=50), db: Session = Depends(get_db)):
    stmt = select(Airport).where(Airport.status != "suspended")
    q = q.strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Airport.iata == q.upper(), Airport.icao == q.upper(), Airport.name.ilike(like),
                Airport.city.ilike(like))
        )
    stmt = stmt.where(Airport.iata.is_not(None)).order_by(
        (Airport.status == "verified").desc(), Airport.name
    ).limit(limit)
    return [serialize(a) for a in db.scalars(stmt)]


@router.get("/{airport_id}")
def detail(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    return serialize(get_airport_or_404(db, airport_id))


@router.get("/{airport_id}/weather")
def weather(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    if not airport.icao:
        return {"icao": None, "metar": None, "taf": None}
    key = f"wx:{airport.icao}"
    hit = cache_get_json(key)
    if hit:
        return hit
    data = fetch_weather(airport.icao)
    if "error" not in data:
        cache_set_json(key, data, settings.weather_cache_ttl)
    return data


def active_notices(db: Session, airport_id: uuid.UUID) -> list[Notice]:
    now = utcnow()
    return list(
        db.scalars(
            select(Notice)
            .where(Notice.airport_id == airport_id, Notice.starts_at <= now,
                   or_(Notice.ends_at.is_(None), Notice.ends_at >= now))
            .order_by(Notice.is_urgent.desc(), Notice.starts_at.desc())
        )
    )


@router.get("/{airport_id}/notices")
def notices(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    get_airport_or_404(db, airport_id)
    return [
        {"id": str(n.id), "title": n.title, "body": n.body, "severity": n.severity, "is_urgent": n.is_urgent,
         "starts_at": n.starts_at.isoformat(), "ends_at": n.ends_at.isoformat() if n.ends_at else None}
        for n in active_notices(db, airport_id)
    ]


@router.get("/{airport_id}/content-version")
def content_version(airport_id: uuid.UUID, db: Session = Depends(get_db)):
    a = get_airport_or_404(db, airport_id)
    return {"version": a.current_published_version, "status": a.status}
