"""JSON cache helpers on the shared Redis client (connection moved to shared.redis)."""
import json
from typing import Any

import structlog

from shared.redis import get_redis

logger = structlog.get_logger(__name__)


async def cache_get(key: str) -> Any | None:
    try:
        redis = await get_redis()
        val = await redis.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        logger.warning("cache_get_failed", key=key, error=str(e))
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    try:
        redis = await get_redis()
        await redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning("cache_set_failed", key=key, error=str(e))


async def cache_delete(key: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception as e:
        logger.warning("cache_delete_failed", key=key, error=str(e))


async def cache_delete_pattern(pattern: str) -> None:
    try:
        redis = await get_redis()
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        logger.warning("cache_delete_pattern_failed", pattern=pattern, error=str(e))
