"""Deterministic demo provider so the app works end to end without API keys."""

import hashlib
from datetime import datetime, timedelta

from app.integrations.flights.base import Flight, FlightProvider

AIRLINES = [("UL", "SriLankan Airlines"), ("EK", "Emirates"), ("QR", "Qatar Airways"), ("SQ", "Singapore Airlines"),
            ("AI", "Air India"), ("TK", "Turkish Airlines"), ("BA", "British Airways"), ("FZ", "flydubai")]
CITIES = [("DXB", "Dubai"), ("DOH", "Doha"), ("SIN", "Singapore"), ("DEL", "Delhi"), ("IST", "Istanbul"),
          ("LHR", "London"), ("BOM", "Mumbai"), ("KUL", "Kuala Lumpur"), ("BKK", "Bangkok"), ("MAA", "Chennai")]


def _h(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)


class MockFlightProvider(FlightProvider):
    name = "mock"

    def get_board(self, iata: str, tz: str, start: datetime, end: datetime) -> list[Flight]:
        flights: list[Flight] = []
        slot = start.replace(minute=(start.minute // 15) * 15, second=0, microsecond=0)
        i = 0
        while slot < end:
            for direction in ("departure", "arrival"):
                seed = _h(iata, direction, slot.isoformat())
                code, airline = AIRLINES[seed % len(AIRLINES)]
                city = CITIES[(seed >> 8) % len(CITIES)]
                if city[0] == iata:
                    continue
                num = f"{code}{100 + (seed >> 16) % 900}"
                delay = [0, 0, 0, 10, 25, 45][(seed >> 24) % 6]
                est = slot + timedelta(minutes=delay)
                now_ref = datetime.now(slot.tzinfo)
                status = "scheduled"
                if delay:
                    status = "delayed"
                if est < now_ref - timedelta(minutes=30):
                    status = "departed" if direction == "departure" else "landed"
                elif direction == "departure" and abs((est - now_ref).total_seconds()) < 2400 and est > now_ref:
                    status = "boarding"
                if (seed >> 30) % 23 == 0:
                    status = "cancelled"
                flights.append(
                    Flight(
                        flight_number=num,
                        airline=airline,
                        direction=direction,
                        other_airport_iata=city[0],
                        other_airport_name=city[1],
                        scheduled=slot.isoformat(),
                        estimated=est.isoformat(),
                        status=status,
                        terminal="T1",
                        gate=f"{'ABC'[(seed >> 4) % 3]}{1 + (seed >> 6) % 14}" if direction == "departure" else None,
                        baggage_belt=str(1 + (seed >> 7) % 6) if direction == "arrival" else None,
                        date=slot.date().isoformat(),
                    )
                )
            slot += timedelta(minutes=20)
            i += 1
        return flights

    def get_flight(self, flight_number: str, date: str) -> list[Flight]:
        seed = _h(flight_number, date)
        base = datetime.fromisoformat(date + "T00:00:00+00:00") + timedelta(hours=6 + seed % 14)
        origin, dest = CITIES[seed % len(CITIES)], CITIES[(seed >> 5) % len(CITIES)]
        if origin == dest:
            dest = CITIES[(seed + 1) % len(CITIES)]
        gate = f"{'ABC'[(seed >> 4) % 3]}{1 + (seed >> 6) % 14}"
        return [
            Flight(flight_number.upper(), "Demo Air", "departure", dest[0], dest[1], base.isoformat(),
                   base.isoformat(), "scheduled", "T1", gate, None, date, {"airport_iata": origin[0]}),
            Flight(flight_number.upper(), "Demo Air", "arrival", origin[0], origin[1],
                   (base + timedelta(hours=4)).isoformat(), (base + timedelta(hours=4)).isoformat(),
                   "scheduled", "T1", None, "3", date, {"airport_iata": dest[0]}),
        ]
