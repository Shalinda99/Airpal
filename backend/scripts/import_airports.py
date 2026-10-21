"""Import airports from OurAirports (public domain): python -m scripts.import_airports [path-or-url] [--all]

By default imports only airports with an IATA code and scheduled service.
"""

import csv
import io
import sys

import httpx
from sqlalchemy import select

from app.db.models import Airport
from app.db.session import SessionLocal

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
TYPES = {"large_airport", "medium_airport", "small_airport"}


def _tz(lat: float, lon: float) -> str:
    try:
        from timezonefinder import TimezoneFinder  # optional dependency

        return TimezoneFinder().timezone_at(lat=lat, lng=lon) or "UTC"
    except ImportError:
        return "UTC"


def main() -> None:
    src = next((a for a in sys.argv[1:] if not a.startswith("--")), URL)
    everything = "--all" in sys.argv
    text = httpx.get(src, timeout=60, follow_redirects=True).text if src.startswith("http") else open(src).read()
    created = updated = 0
    with SessionLocal() as db:
        existing = {a.ourairports_id: a for a in db.scalars(select(Airport)) if a.ourairports_id}
        for row in csv.DictReader(io.StringIO(text)):
            if row["type"] not in TYPES or (not everything and (not row["iata_code"] or row["scheduled_service"] != "yes")):
                continue
            oid = int(row["id"])
            lat, lon = float(row["latitude_deg"]), float(row["longitude_deg"])
            a = existing.get(oid)
            if a:
                updated += 1
            else:
                a = Airport(ourairports_id=oid, status="basic", tz=_tz(lat, lon))
                db.add(a)
                created += 1
            a.iata = row["iata_code"] or None
            a.icao = row["gps_code"] or row["ident"] or None
            a.name, a.city, a.country = row["name"], row["municipality"] or None, row["iso_country"]
            a.region, a.lat, a.lon = row["iso_region"], lat, lon
        db.commit()
    print(f"created={created} updated={updated}")


if __name__ == "__main__":
    main()
