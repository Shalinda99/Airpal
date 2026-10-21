from app.core.config import settings
from app.integrations.flights.aerodatabox import AeroDataBoxProvider
from app.integrations.flights.base import FlightProvider
from app.integrations.flights.mock import MockFlightProvider


def get_flight_provider() -> FlightProvider:
    if settings.flight_provider == "aerodatabox":
        return AeroDataBoxProvider()
    return MockFlightProvider()
