"""Agent tools. Each returns {"name", "title", "text", "data"}; text is what the model may rely on."""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Airport, Ticket, User
from app.integrations.weather import fetch_weather
from app.modules.flights.service import get_flight_status
from app.modules.journey.gates import gate_walk_minutes
from app.modules.rides.router import ride_options
from app.modules.support.router import support_options

FLIGHT_RE = re.compile(r"\b([A-Za-z0-9]{2}\s?\d{1,4})\b")
GATE_RE = re.compile(r"\bgate\s+([A-Za-z]?\d{1,3})\b", re.I)


def get_flight_status_tool(airport: Airport, flight_number: str, date: str | None = None) -> dict:
    date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    legs = get_flight_status(flight_number, date)
    legs = [leg for leg in legs if leg.get("extra", {}).get("airport_iata") in (None, airport.iata)] or legs
    if not legs:
        return {"name": "get_flight_status", "title": f"Live flight data {flight_number}", "text": "", "data": []}
    leg = legs[0]
    text = (f"Flight {flight_number.upper()} on {date}: {leg['direction']} status {leg['status']}, scheduled "
            f"{leg['scheduled']}, estimated {leg['estimated']}, terminal {leg.get('terminal') or 'n/a'}, gate "
            f"{leg.get('gate') or 'not assigned yet'}.")
    return {"name": "get_flight_status", "title": f"Live flight data {flight_number.upper()}", "text": text,
            "data": leg}


def get_airport_weather_tool(airport: Airport) -> dict:
    if not airport.icao:
        return {"name": "get_airport_weather", "title": "Weather", "text": "", "data": None}
    wx = fetch_weather(airport.icao)
    metar = (wx.get("metar") or {}).get("raw")
    taf = (wx.get("taf") or {}).get("raw")
    text = " ".join(x for x in (f"METAR: {metar}" if metar else "", f"TAF: {taf}" if taf else "") if x)
    return {"name": "get_airport_weather", "title": "Aviation weather (METAR/TAF)", "text": text, "data": wx}


def get_gate_walk_time_tool(db: Session, airport: Airport, gate: str) -> dict:
    mins = gate_walk_minutes(db, airport, gate)
    text = f"Published walking time from security to gate {gate.upper()}: {mins} minutes." if mins else ""
    return {"name": "get_gate_walk_time", "title": f"Gate {gate.upper()} walking time", "text": text, "data": mins}


def get_user_ticket_tool(db: Session, user: User | None) -> dict:
    if not user:
        return {"name": "get_user_ticket", "title": "Your ticket", "text": "", "data": None}
    t = db.scalar(select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.flight_date).limit(1))
    if not t:
        return {"name": "get_user_ticket", "title": "Your ticket", "text": "", "data": None}
    text = (f"Your ticket: flight {t.flight_number} on {t.flight_date}, seat {t.seat or 'n/a'}, gate "
            f"{t.gate or 'not assigned yet'}, terminal {t.terminal or 'n/a'}, boarding "
            f"{t.boarding_time.isoformat() if t.boarding_time else 'unknown'}.")
    return {"name": "get_user_ticket", "title": "Your ticket", "text": text, "data": {"flight": t.flight_number}}


def get_ride_options_tool(db: Session, airport: Airport) -> dict:
    opts = ride_options(db, airport)
    parts = []
    for p in opts["pickup_points"]:
        parts.append(f"Pickup point {p['zone_name']} ({p.get('terminal') or 'airport'}, level {p.get('level') or 'n/a'}): "
                     f"{p.get('walking_instructions') or ''} {p.get('notes') or ''}".strip())
    if opts["providers"]:
        parts.append("Ride options: " + ", ".join(x["label"] for x in opts["providers"]) + ".")
    return {"name": "get_ride_options", "title": "Ride pickup and options", "text": " ".join(parts), "data": opts}


def get_support_options_tool(db: Session, airport: Airport) -> dict:
    opts = support_options(db, airport)
    text = "; ".join(f"{o['type']}: {o['value']} ({'open now' if o['open_now'] else 'closed now'})" for o in opts)
    return {"name": "get_support_options", "title": "Customer care", "text": text, "data": opts}
