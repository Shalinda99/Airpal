import json
import logging
import re
import sys
import time

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_PNR = re.compile(r"\b(?:PNR|booking(?: ref(?:erence)?)?)[:\s#]*([A-Z0-9]{5,7})\b", re.I)


def redact_pii(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _PNR.sub("PNR [redacted]", text)
    return _PHONE.sub("[phone]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_pii(record.getMessage()),
        }
        for k in ("request_id", "path", "status", "duration_ms"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)
