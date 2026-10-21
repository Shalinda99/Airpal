"""Smart ride timing. Pure functions, durations come from the airport's published answers."""

from datetime import datetime, timedelta

DEFAULTS = {
    "queue_checkin_minutes": 15,
    "queue_security_minutes": 15,
    "emigration_minutes": 10,
    "immigration_minutes": 20,
    "baggage_minutes": 20,
    "boarding_close_minutes": 15,
    "bag_drop_cutoff": 60,
    "gate_walk_minutes": 10,
    "exit_walk_minutes": 10,
}
SAFETY_MARGIN = 10
PICKUP_WAIT = 8  # typical time for a ride to arrive


def _d(durations: dict, key: str) -> int:
    v = durations.get(key)
    return int(v) if isinstance(v, (int, float)) and v >= 0 else DEFAULTS[key]


def compute_to_airport(departure: datetime, travel_min: int, durations: dict, international: bool,
                       has_checked_bag: bool) -> dict:
    """Home -> Airport. Works backwards from flight departure."""
    process = (
        (_d(durations, "queue_checkin_minutes") if has_checked_bag else 0)
        + _d(durations, "queue_security_minutes")
        + (_d(durations, "emigration_minutes") if international else 0)
        + _d(durations, "gate_walk_minutes")
        + _d(durations, "boarding_close_minutes")
        + SAFETY_MARGIN
    )
    if has_checked_bag:
        process = max(process, _d(durations, "bag_drop_cutoff") + _d(durations, "queue_checkin_minutes"))
    arrive_at_airport = departure - timedelta(minutes=process)
    leave_by = arrive_at_airport - timedelta(minutes=travel_min)
    book_at = leave_by - timedelta(minutes=PICKUP_WAIT)
    return {
        "kind": "to_airport", "airport_process_minutes": process, "travel_minutes": travel_min,
        "arrive_at_airport": arrive_at_airport, "leave_by": leave_by, "book_at": book_at,
    }


def compute_from_airport(arrival: datetime, travel_min: int, durations: dict, international: bool,
                         has_checked_bag: bool) -> dict:
    """Airport -> anywhere. Works forwards from landing."""
    process = (
        (_d(durations, "immigration_minutes") if international else 0)
        + (_d(durations, "baggage_minutes") if has_checked_bag else 0)
        + _d(durations, "exit_walk_minutes")
    )
    ready_at_exit = arrival + timedelta(minutes=process)
    book_at = ready_at_exit - timedelta(minutes=PICKUP_WAIT)
    return {
        "kind": "from_airport", "airport_process_minutes": process, "travel_minutes": travel_min,
        "ready_at_pickup": ready_at_exit, "book_at": book_at, "leave_by": ready_at_exit,
        "estimated_arrival_at_destination": ready_at_exit + timedelta(minutes=PICKUP_WAIT + travel_min),
    }


def compute_arrive_by(arrive_by: datetime, travel_min: int) -> dict:
    """Home -> Airport with explicit 'arrive by' time (no flight)."""
    leave_by = arrive_by - timedelta(minutes=travel_min)
    return {"kind": "to_airport", "airport_process_minutes": 0, "travel_minutes": travel_min,
            "arrive_at_airport": arrive_by, "leave_by": leave_by, "book_at": leave_by - timedelta(minutes=PICKUP_WAIT)}


def serialize(result: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in result.items()}
