"""AeroDataBox (RapidAPI) adapter. Check current pricing/terms at https://aerodatabox.com before production use."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.integrations.flights.base import Flight, FlightProvider, ProviderError, ProviderRateLimited

_STATUS = {
    "expected": "scheduled",
    "enroute": "departed",
    "checkin": "scheduled",
    "boarding": "boarding",
    "gateclosed": "boarding",
    "departed": "departed",
    "delayed": "delayed",
    "approaching": "departed",
    "arrived": "landed",
    "canceled": "cancelled",
    "canceleduncertain": "cancelled",
}


def _utc(node: dict | None) -> str | None:
    if not node:
        return None
    v = node.get("utc")
    if not v:
        return None
    return v.replace(" ", "T").replace("Z", "+00:00") if "+" in v or "Z" in v else v.replace(" ", "T") + "+00:00"


def _to_flight(item: dict, direction: str) -> Flight:
    mv = item.get("movement") or {}
    sched = _utc(mv.get("scheduledTime"))
    est = _utc(mv.get("revisedTime")) or _utc(mv.get("predictedTime"))
    status = _STATUS.get(str(item.get("status", "")).lower(), "unknown")
    if status == "scheduled" and sched and est and est > sched:
        status = "delayed"
    return Flight(
        flight_number=str(item.get("number", "")).replace(" ", ""),
        airline=(item.get("airline") or {}).get("name"),
        direction=direction,
        other_airport_iata=(mv.get("airport") or {}).get("iata"),
        other_airport_name=(mv.get("airport") or {}).get("name"),
        scheduled=sched,
        estimated=est,
        status=status,
        terminal=mv.get("terminal"),
        gate=mv.get("gate"),
        baggage_belt=mv.get("baggageBelt"),
        date=sched[:10] if sched else None,
    )


class AeroDataBoxProvider(FlightProvider):
    name = "aerodatabox"

    def _get(self, path: str, params: dict | None = None):
        if not settings.aerodatabox_api_key:
            raise ProviderError("AERODATABOX_API_KEY not configured")
        try:
            r = httpx.get(
                f"https://{settings.aerodatabox_host}{path}",
                params=params,
                headers={
                    "X-RapidAPI-Key": settings.aerodatabox_api_key,
                    "X-RapidAPI-Host": settings.aerodatabox_host,
                },
                timeout=10,
            )
        except httpx.HTTPError as e:
            raise ProviderError(str(e)) from e
        if r.status_code == 429:
            raise ProviderRateLimited("AeroDataBox rate limit")
        if r.status_code == 204 or r.status_code == 404:
            return {}
        if r.status_code >= 400:
            raise ProviderError(f"AeroDataBox HTTP {r.status_code}")
        return r.json()

    def get_board(self, iata: str, tz: str, start: datetime, end: datetime) -> list[Flight]:
        zone = ZoneInfo(tz)
        fmt = "%Y-%m-%dT%H:%M"
        a = start.astimezone(zone).strftime(fmt)
        b = end.astimezone(zone).strftime(fmt)
        data = self._get(
            f"/flights/airports/iata/{iata}/{a}/{b}",
            {"direction": "Both", "withCancelled": "true", "withCodeshared": "false", "withLeg": "false"},
        )
        out = [_to_flight(i, "departure") for i in data.get("departures", [])]
        out += [_to_flight(i, "arrival") for i in data.get("arrivals", [])]
        return out

    def get_flight(self, flight_number: str, date: str) -> list[Flight]:
        data = self._get(f"/flights/number/{flight_number}/{date}")
        items = data if isinstance(data, list) else []
        flights: list[Flight] = []
        for it in items:
            dep, arr = it.get("departure") or {}, it.get("arrival") or {}
            for direction, side, other in (("departure", dep, arr), ("arrival", arr, dep)):
                sched = _utc(side.get("scheduledTime"))
                est = _utc(side.get("revisedTime")) or _utc(side.get("predictedTime"))
                status = _STATUS.get(str(it.get("status", "")).lower(), "unknown")
                flights.append(
                    Flight(
                        flight_number=flight_number.upper(),
                        airline=(it.get("airline") or {}).get("name"),
                        direction=direction,
                        other_airport_iata=(other.get("airport") or {}).get("iata"),
                        other_airport_name=(other.get("airport") or {}).get("name"),
                        scheduled=sched,
                        estimated=est,
                        status=status,
                        terminal=side.get("terminal"),
                        gate=side.get("gate"),
                        baggage_belt=side.get("baggageBelt"),
                        date=date,
                        extra={"airport_iata": (side.get("airport") or {}).get("iata")},
                    )
                )
        return flights


def now_utc() -> datetime:
    return datetime.now(UTC)
