from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime


class ProviderError(Exception):
    pass


class ProviderRateLimited(ProviderError):
    pass


@dataclass
class Flight:
    flight_number: str
    airline: str | None
    direction: str  # departure|arrival
    other_airport_iata: str | None
    other_airport_name: str | None
    scheduled: str | None  # ISO-8601 UTC
    estimated: str | None
    status: str  # scheduled|boarding|departed|delayed|landed|cancelled|unknown
    terminal: str | None = None
    gate: str | None = None
    baggage_belt: str | None = None
    date: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class FlightProvider(ABC):
    name: str

    @abstractmethod
    def get_board(self, iata: str, tz: str, start: datetime, end: datetime) -> list[Flight]:
        """Departures and arrivals at an airport for a UTC window (<= 12h)."""

    @abstractmethod
    def get_flight(self, flight_number: str, date: str) -> list[Flight]:
        """Legs of a flight number on a local date (YYYY-MM-DD)."""
