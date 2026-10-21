from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.integrations.rides.base import Place
from app.integrations.rides.providers import build_booking_link
from app.integrations.routing import haversine_km
from app.modules.journey.gates import parse_walk_minutes
from app.modules.rides import timing
from app.modules.tickets.bcbp import BCBPError, decode_bcbp

SAMPLE = "M1DESMARAIS/LUC       EABC123 YULFRAAC 0834 226F001A0025 100"


def test_bcbp_decode():
    bp = decode_bcbp(SAMPLE, today=date(2026, 8, 14))
    assert bp.passenger_name == "Luc Desmarais"
    assert (bp.pnr, bp.origin, bp.destination) == ("ABC123", "YUL", "FRA")
    assert bp.flight_number == "AC834"
    assert bp.flight_date == "2026-08-14"  # day 226
    assert bp.seat == "1A"


def test_bcbp_invalid():
    with pytest.raises(BCBPError):
        decode_bcbp("hello")


def test_to_airport_timing_international_bag():
    dep = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    r = timing.compute_to_airport(dep, 40, {"queue_security_minutes": 20}, True, True)
    assert r["airport_process_minutes"] >= 75  # bag drop cutoff 60 + checkin queue 15
    assert r["leave_by"] == r["arrive_at_airport"] - timedelta(minutes=40)
    assert r["book_at"] < r["leave_by"]


def test_from_airport_timing():
    arr = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    r = timing.compute_from_airport(arr, 30, {"immigration_minutes": 30, "baggage_minutes": 20}, True, True)
    assert r["airport_process_minutes"] == 60
    assert r["ready_at_pickup"] == arr + timedelta(minutes=60)


def test_uber_link_has_required_params():
    res = build_booking_link("uber", Place(current_location=True),
                             Place(lat=7.1, lon=79.9, nickname="Hotel Lanka", formatted_address="1 Beach Rd"))
    q = parse_qs(urlparse(res["web_link"]).query)
    assert q["action"] == ["setPickup"] and q["pickup"] == ["my_location"]
    assert q["dropoff[latitude]"] == ["7.100000"] and q["dropoff[nickname]"] == ["Hotel Lanka"]
    assert res["app_link"].startswith("uber://?")


def test_uber_requires_dropoff_label():
    with pytest.raises(ValueError):
        build_booking_link("uber", Place(current_location=True), Place(lat=1, lon=1))


def test_gate_walk_parse():
    text = "A1-A10: 8\nB1-B12: 12"
    assert parse_walk_minutes(text, "B7") == 12
    assert parse_walk_minutes(text, "A10") == 8
    assert parse_walk_minutes(text, "C1") is None


def test_haversine():
    assert 400 < haversine_km(51.47, -0.45, 48.35, 2.55) < 415
