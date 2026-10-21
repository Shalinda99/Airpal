from urllib.parse import quote, urlencode

from app.core.config import settings
from app.integrations.rides.base import Place, RideProvider

UBER_UNIVERSAL = "https://m.uber.com/ul/"
UBER_SCHEME = "uber://"


def _place_params(prefix: str, p: Place) -> dict[str, str]:
    params: dict[str, str] = {}
    if prefix == "pickup" and p.current_location:
        return {"pickup": "my_location"}
    if p.lat is None or p.lon is None:
        return params
    params[f"{prefix}[latitude]"] = f"{p.lat:.6f}"
    params[f"{prefix}[longitude]"] = f"{p.lon:.6f}"
    # Uber needs a nickname or formatted address so the destination label shows in the app.
    nick = p.nickname or p.formatted_address
    if nick:
        params[f"{prefix}[nickname]"] = nick
    if p.formatted_address:
        params[f"{prefix}[formatted_address]"] = p.formatted_address
    return params


class UberDeepLinkProvider(RideProvider):
    """Uber via universal/deep links. No API approval needed; opens the Uber app (web fallback)."""

    key = "uber"
    label = "Uber"

    def build_booking_link(self, pickup: Place, dropoff: Place, options: dict | None = None) -> dict:
        if (dropoff.lat is None or dropoff.lon is None) or not (dropoff.nickname or dropoff.formatted_address):
            raise ValueError("dropoff needs coordinates and a nickname or formatted address")
        params: dict[str, str] = {"action": "setPickup"}
        if settings.uber_client_id:
            params["client_id"] = settings.uber_client_id
        params |= _place_params("pickup", pickup)
        params |= _place_params("dropoff", dropoff)
        qs = urlencode(params, quote_via=quote, safe="")
        return {
            "provider": self.key,
            "label": self.label,
            "app_link": f"{UBER_SCHEME}?{qs}",
            "web_link": f"{UBER_UNIVERSAL}?{qs}",  # fallback when the Uber app is not installed
            "price_estimate": None,
            "note": "Open in Uber to see price",
            "client_id_configured": bool(settings.uber_client_id),
        }


class UberRidesApiProvider(RideProvider):
    """EXTENSION POINT: in-app requests and status tracking via Uber Rides API (requires Uber approval)."""

    key = "uber_api"
    label = "Uber (in-app)"
    supports_estimates = True

    def build_booking_link(self, pickup: Place, dropoff: Place, options: dict | None = None) -> dict:
        raise NotImplementedError("Uber Rides API integration requires Uber approval")

    def get_estimates(self, pickup: Place, dropoff: Place) -> dict | None:
        raise NotImplementedError("Uber Rides API integration requires Uber approval")


class StubLinkProvider(RideProvider):
    """Placeholder for providers without a public deep link integration yet (Bolt, PickMe, Grab)."""

    def __init__(self, key: str, label: str, web: str | None = None):
        self.key, self.label, self._web = key, label, web

    def build_booking_link(self, pickup: Place, dropoff: Place, options: dict | None = None) -> dict:
        return {"provider": self.key, "label": self.label, "app_link": None, "web_link": self._web,
                "price_estimate": None, "note": f"Open {self.label} and enter your destination"}


class InfoProvider(RideProvider):
    """Official taxi desk, shuttle, metro/bus: shows airport-provided instructions only."""

    def __init__(self, key: str, label: str):
        self.key, self.label = key, label

    def build_booking_link(self, pickup: Place, dropoff: Place, options: dict | None = None) -> dict:
        cfg = (options or {}).get("config") or {}
        return {"provider": self.key, "label": self.label, "app_link": None, "web_link": cfg.get("url"),
                "price_estimate": cfg.get("price_hint"), "note": cfg.get("info") or "See airport information"}


REGISTRY: dict[str, RideProvider] = {
    "uber": UberDeepLinkProvider(),
    "bolt": StubLinkProvider("bolt", "Bolt", "https://bolt.eu"),
    "pickme": StubLinkProvider("pickme", "PickMe", "https://pickme.lk"),
    "grab": StubLinkProvider("grab", "Grab", "https://www.grab.com"),
    "taxi_desk": InfoProvider("taxi_desk", "Official taxi desk"),
    "shuttle": InfoProvider("shuttle", "Airport shuttle"),
    "public_transport": InfoProvider("public_transport", "Metro / bus"),
}


def build_booking_link(provider: str, pickup: Place, dropoff: Place, options: dict | None = None) -> dict:
    if provider not in REGISTRY:
        raise KeyError(provider)
    return REGISTRY[provider].build_booking_link(pickup, dropoff, options)
