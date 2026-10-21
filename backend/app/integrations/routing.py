import math

import httpx

from app.core.config import settings


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _haversine_minutes(o: tuple[float, float], d: tuple[float, float]) -> int:
    return max(5, int(haversine_km(*o, *d) * 1.3 / 35 * 60))


def travel_minutes(origin: tuple[float, float], dest: tuple[float, float]) -> tuple[int, str]:
    """Driving minutes with a 15% buffer. Returns (minutes, source). Provider-pluggable via ROUTING_PROVIDER."""
    try:
        if settings.routing_provider == "google" and settings.google_maps_api_key:
            r = httpx.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": f"{origin[0]},{origin[1]}", "destinations": f"{dest[0]},{dest[1]}",
                        "departure_time": "now", "key": settings.google_maps_api_key},
                timeout=6,
            )
            el = r.json()["rows"][0]["elements"][0]
            secs = el.get("duration_in_traffic", el["duration"])["value"]
            return math.ceil(secs / 60), "google"
        if settings.routing_provider == "osrm":
            url = f"{settings.osrm_url}/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
            r = httpx.get(url, params={"overview": "false"}, timeout=6)
            r.raise_for_status()
            secs = r.json()["routes"][0]["duration"]
            return math.ceil(secs * 1.15 / 60), "osrm"
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        pass
    return _haversine_minutes(origin, dest), "haversine"
