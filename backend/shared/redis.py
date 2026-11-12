"""One Redis client per process. Merged from the per-service core/redis.py and
restaurant-svc's core/cache.py connection code (they were identical apart from
the explicit utf-8 encoding, which is redis-py's default anyway)."""
from redis.asyncio import BlockingConnectionPool, Redis

from shared.config import get_settings

settings = get_settings()

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        # P24: a known pool size that waits briefly for a free connection instead
        # of failing the request ("Too many connections").
        pool = BlockingConnectionPool.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
            encoding="utf-8",
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            timeout=5,
        )
        _redis_client = Redis.from_pool(pool)  # closing the client closes its pool
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
