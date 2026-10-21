import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Airport, PublishVersion

_RANGE = re.compile(r"^\s*([A-Za-z]*)(\d+)\s*(?:-\s*([A-Za-z]*)(\d+))?\s*[:\-=]\s*(\d+)")


def parse_walk_minutes(text: str, gate: str) -> int | None:
    m = re.fullmatch(r"\s*([A-Za-z]*)(\d+)\s*", gate or "")
    if not m:
        return None
    prefix, num = m.group(1).upper(), int(m.group(2))
    for line in text.splitlines():
        r = _RANGE.match(line)
        if not r:
            continue
        p1, n1, _p2, n2, mins = r.group(1).upper(), int(r.group(2)), r.group(3), r.group(4), int(r.group(5))
        hi = int(n2) if n2 else n1
        if p1 == prefix and n1 <= num <= hi:
            return mins
    return None


def gate_walk_minutes(db: Session, airport: Airport, gate: str) -> int | None:
    row = db.scalar(select(PublishVersion).where(PublishVersion.airport_id == airport.id,
                                                 PublishVersion.version_no == airport.current_published_version))
    text = (row.snapshot.get("gate_walking_times") if row else None) or ""
    return parse_walk_minutes(text, gate)
