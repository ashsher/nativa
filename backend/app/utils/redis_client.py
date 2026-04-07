"""
app/utils/redis_client.py — Async Redis connection pool and helper functions.

A single connection pool is created at module-import time and reused for
every request.  All cache helpers are thin wrappers that encode/decode JSON
so callers can store arbitrary Python objects.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import settings

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------
# decode_responses=True makes all returned values str instead of bytes, which
# saves manual .decode() calls throughout the codebase.
_pool: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


def get_redis() -> aioredis.Redis:
    """
    Return the shared async Redis client.

    Usage:
        redis = get_redis()
        await redis.ping()
    """
    return _pool


async def set_cache(key: str, value: Any, ttl: int) -> None:
    """
    Serialise *value* to JSON and store it in Redis with a TTL in seconds.

    Args:
        key:   Redis key string.
        value: Any JSON-serialisable Python object.
        ttl:   Time-to-live in seconds.
    """
    redis = get_redis()
    # json.dumps handles dicts, lists, strings, numbers, None.
    await redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))


async def get_cache(key: str) -> Optional[Any]:
    """
    Retrieve and deserialise a cached value by key.

    Returns None if the key does not exist or has expired.
    """
    redis = get_redis()
    raw = await redis.get(key)
    if raw is None:
        return None
    # Deserialise from JSON back to the original Python object.
    return json.loads(raw)


async def delete_cache(key: str) -> None:
    """Delete a cache entry immediately (e.g. to invalidate stale data)."""
    redis = get_redis()
    await redis.delete(key)


async def hincrby(key: str, field: str, amount: int = 1) -> int:
    """
    Atomically increment an integer field inside a Redis hash.

    Used by quota_service to increment daily usage counters.

    Returns the new value of the field after the increment.
    """
    redis = get_redis()
    return await redis.hincrby(key, field, amount)


async def hget(key: str, field: str) -> Optional[str]:
    """
    Get the string value of a field in a Redis hash.

    Returns None if the key or field does not exist.
    """
    redis = get_redis()
    return await redis.hget(key, field)


async def expire(key: str, ttl: int) -> None:
    """
    Set or refresh the TTL on an existing Redis key.

    Args:
        key: Redis key.
        ttl: Time-to-live in seconds from now.
    """
    redis = get_redis()
    await redis.expire(key, ttl)
