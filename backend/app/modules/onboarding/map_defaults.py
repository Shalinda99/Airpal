"""Default map flow, used when an airport has not edited its own. (type, label, walking minutes to next, notes)"""

_ENT = ("entrance", "Terminal entrance", 3, None)
_CHECKIN = ("check_in", "Check-in", 4, None)
_SEC = ("security", "Security", 5, None)
_IMM_OUT = ("emigration", "Passport control", 4, None)
_GATE = ("gate_zone", "Gate zone", 0, None)

DEFAULT_MAPS: dict[tuple[str, str], list[tuple[str, str, int, str | None]]] = {
    ("departure", "domestic"): [_ENT, _CHECKIN, _SEC, _GATE],
    ("departure", "international"): [_ENT, _CHECKIN, _SEC, _IMM_OUT, _GATE],
    ("arrival", "domestic"): [("gate_zone", "Arrival gate", 6, None), ("baggage", "Baggage claim", 3, None),
                              ("exit", "Arrivals exit", 0, None)],
    ("arrival", "international"): [("gate_zone", "Arrival gate", 6, None), ("immigration", "Immigration", 4, None),
                                   ("baggage", "Baggage claim", 3, None), ("customs", "Customs", 3, None),
                                   ("exit", "Arrivals exit", 0, None)],
    ("transit", "domestic"): [("gate_zone", "Arrival gate", 5, None), ("transfer_desk", "Transfer desk", 5, None),
                              ("gate_zone", "Departure gate", 0, None)],
    ("transit", "international"): [("gate_zone", "Arrival gate", 5, None), ("transfer_desk", "Transfer desk", 4, None),
                                   ("security", "Transfer security", 5, None), ("gate_zone", "Departure gate", 0, None)],
}
