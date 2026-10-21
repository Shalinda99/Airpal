"""Cache with Redis backend and in-memory fallback (dev/tests)."""

import json
import time
from typing import Any

from app.core.config import settings


class _MemoryCache:
    def __init__(self) -> None:
        self._d: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str | None:
        item = self._d.get(key)
        if not item:
            return None
        if item[0] < time.time():
            self._d.pop(key, None)
            return None
        return item[1]

    def set(self, key: str, value: str, ttl: int) -> None:
        self._d[key] = (time.time() + ttl, value)

    def incr(self, key: str, ttl: int) -> int:
        cur = self.get(key)
        n = int(cur) + 1 if cur else 1
        exp = self._d[key][0] if cur else time.time() + ttl
        self._d[key] = (exp, str(n))
        return n

    def delete(self, key: str) -> None:
        self._d.pop(key, None)

    def clear(self) -> None:
        self._d.clear()


class _RedisCache:
    def __init__(self, url: str) -> None:
        import redis

        self.r = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self.r.get(key)

    def set(self, key: str, value: str, ttl: int) -> None:
        self.r.set(key, value, ex=ttl)

    def incr(self, key: str, ttl: int) -> int:
        p = self.r.pipeline()
        p.incr(key)
        p.expire(key, ttl, nx=True)
        return int(p.execute()[0])

    def delete(self, key: str) -> None:
        self.r.delete(key)

    def clear(self) -> None:
        self.r.flushdb()


_backend = _RedisCache(settings.redis_url) if settings.redis_url else _MemoryCache()


def cache_get_json(key: str) -> Any | None:
    try:
        raw = _backend.get(key)
    except Exception:
        return None
    return json.loads(raw) if raw else None


def cache_set_json(key: str, value: Any, ttl: int) -> None:
    try:
        _backend.set(key, json.dumps(value, default=str), ttl)
    except Exception:
        pass


def cache_incr(key: str, ttl: int) -> int:
    try:
        return _backend.incr(key, ttl)
    except Exception:
        return 0


def cache_delete(key: str) -> None:
    try:
        _backend.delete(key)
    except Exception:
        pass


def cache_clear() -> None:
    _backend.clear()


def cache_ping() -> bool:
    try:
        if isinstance(_backend, _RedisCache):
            return bool(_backend.r.ping())
        return True
    except Exception:
        return False
