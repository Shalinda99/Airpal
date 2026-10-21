"""METAR/TAF from aviationweather.gov (free, no key)."""

import httpx

BASE = "https://aviationweather.gov/api/data"


def fetch_weather(icao: str) -> dict:
    out: dict = {"icao": icao, "metar": None, "taf": None, "source": "aviationweather.gov"}
    try:
        m = httpx.get(f"{BASE}/metar", params={"ids": icao, "format": "json"}, timeout=8)
        if m.status_code == 200 and m.text.strip():
            d = m.json()
            if d:
                row = d[0]
                out["metar"] = {
                    "raw": row.get("rawOb"),
                    "temp_c": row.get("temp"),
                    "wind_dir": row.get("wdir"),
                    "wind_kt": row.get("wspd"),
                    "visibility": row.get("visib"),
                    "clouds": row.get("clouds"),
                    "observed": row.get("reportTime"),
                }
        t = httpx.get(f"{BASE}/taf", params={"ids": icao, "format": "json"}, timeout=8)
        if t.status_code == 200 and t.text.strip():
            d = t.json()
            if d:
                out["taf"] = {"raw": d[0].get("rawTAF")}
    except (httpx.HTTPError, ValueError):
        out["error"] = "weather_unavailable"
    return out
