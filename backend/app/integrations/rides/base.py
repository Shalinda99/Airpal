from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Place:
    lat: float | None = None
    lon: float | None = None
    nickname: str | None = None
    formatted_address: str | None = None
    current_location: bool = False  # pickup only: use the device's current location


class RideProvider(ABC):
    key: str
    label: str
    supports_estimates: bool = False

    @abstractmethod
    def build_booking_link(self, pickup: Place, dropoff: Place, options: dict | None = None) -> dict:
        """Return {provider, label, app_link, web_link, note}. Links may be None for info-only providers."""

    def get_estimates(self, pickup: Place, dropoff: Place) -> dict | None:
        """Optional price/ETA estimate. None => provider does not support it."""
        return None
