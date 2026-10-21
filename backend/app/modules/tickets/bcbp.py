"""IATA BCBP (Resolution 792) decoder for the mandatory unique + repeated fields of the first leg."""

import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta


class BCBPError(ValueError):
    pass


@dataclass
class BoardingPass:
    passenger_name: str
    pnr: str
    origin: str
    destination: str
    carrier: str
    flight_number: str
    julian_day: int
    flight_date: str  # YYYY-MM-DD (year inferred nearest to today)
    seat: str | None
    sequence: str | None
    legs: int

    def to_dict(self) -> dict:
        return asdict(self)


def julian_to_date(day: int, today: date | None = None) -> date:
    today = today or datetime.now(UTC).date()
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            d = date(year, 1, 1) + timedelta(days=day - 1)
        except (ValueError, OverflowError):
            continue
        if d.year != year:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    if best is None:
        raise BCBPError("Invalid day of year")
    return best


def decode_bcbp(raw: str, today: date | None = None) -> BoardingPass:
    s = raw.strip("\r\n")
    if len(s) < 60 or s[0] != "M":
        raise BCBPError("Not a valid BCBP string")
    try:
        legs = int(s[1])
    except ValueError:
        raise BCBPError("Invalid number of legs") from None
    name = s[2:22].strip()
    pnr = s[23:30].strip()
    origin, dest = s[30:33], s[33:36]
    carrier = s[36:39].strip()
    flight = s[39:44].strip().lstrip("0") or "0"
    if not (re.fullmatch(r"[A-Z]{3}", origin) and re.fullmatch(r"[A-Z]{3}", dest)):
        raise BCBPError("Invalid airport codes")
    try:
        jd = int(s[44:47])
    except ValueError:
        raise BCBPError("Invalid flight date") from None
    seat = s[48:52].strip().lstrip("0") or None
    seq = s[52:57].strip() or None
    d = julian_to_date(jd, today)
    pretty_name = " ".join(reversed(name.split("/", 1))).title() if "/" in name else name.title()
    return BoardingPass(pretty_name, pnr, origin, dest, carrier, f"{carrier}{flight}", jd, d.isoformat(), seat, seq,
                        legs)
