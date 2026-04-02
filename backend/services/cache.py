"""Redis cache layer with dict fallback."""
import json
import logging
from time import time

import redis

from backend.config import REDIS_URL

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None
_fallback: dict[str, tuple[float, str]] = {}


def _get_redis() -> redis.Redis | None:
    global _redis
    if _redis is not None:
        return _redis
    try:
        _redis = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
        _redis.ping()
        return _redis
    except Exception as e:
        logger.warning("Redis unavailable, using dict fallback: %s", e)
        _redis = None
        return None


def cache_get(key: str) -> dict | list | None:
    r = _get_redis()
    if r:
        try:
            val = r.get(key)
            return json.loads(val) if val else None
        except Exception:
            pass
    # Dict fallback
    if key in _fallback:
        exp, val = _fallback[key]
        if time() < exp:
            return json.loads(val)
        del _fallback[key]
    return None


def cache_set(key: str, value, ttl: int = 60):
    data = json.dumps(value, ensure_ascii=False)
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl, data)
            return
        except Exception:
            pass
    _fallback[key] = (time() + ttl, data)


def cache_delete_pattern(pattern: str):
    r = _get_redis()
    if r:
        try:
            for key in r.scan_iter(match=pattern):
                r.delete(key)
            return
        except Exception:
            pass
    keys_to_del = [k for k in _fallback if _matches_pattern(k, pattern)]
    for k in keys_to_del:
        del _fallback[k]


def _matches_pattern(key: str, pattern: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(key, pattern)
