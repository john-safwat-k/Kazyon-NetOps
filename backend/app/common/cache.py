"""Redis cache-aside helpers and distributed lock coordination."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis

from .config import get_settings

logger = logging.getLogger("it_net.cache")

_redis_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Return a shared Redis client, or None if Redis is disabled/unreachable."""
    global _redis_client
    settings = get_settings()
    if not settings.cache_enabled:
        return None
    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        except Exception as exc:
            logger.warning("Failed to initialize Redis client: %s", exc)
            return None
    return _redis_client


def cache_get_json(key: str) -> Optional[Any]:
    """Read and deserialize a JSON value from Redis (fail-open on Redis error)."""
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(str(raw)) if raw is not None else None
    except Exception as exc:
        logger.debug("Redis cache_get_json miss/error for %s: %s", key, exc)
        return None


def cache_set_json(key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
    """Serialize and store a JSON value in Redis with TTL (fail-open on Redis error)."""
    client = get_redis()
    if client is None:
        return
    ttl = ttl_sec if ttl_sec is not None else get_settings().cache_default_ttl_sec
    try:
        client.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.debug("Redis cache_set_json error for %s: %s", key, exc)


def cache_delete(key: str) -> None:
    """Invalidate a cached key in Redis."""
    client = get_redis()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception as exc:
        logger.debug("Redis cache_delete error for %s: %s", key, exc)
