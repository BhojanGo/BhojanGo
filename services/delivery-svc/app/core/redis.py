import json
from typing import Any

import structlog
from redis.asyncio import Redis, from_url

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ── Driver location keys ──────────────────────────────────────────────────────

def driver_location_key(driver_id: str) -> str:
    return f"driver:{driver_id}:location"


def order_tracking_channel(order_id: str) -> str:
    return f"tracking:{order_id}"


async def store_driver_location(driver_id: str, location: dict[str, Any]) -> None:
    redis = await get_redis()
    await redis.setex(
        driver_location_key(driver_id),
        settings.DRIVER_LOCATION_TTL,
        json.dumps(location),
    )


async def get_driver_location(driver_id: str) -> dict[str, Any] | None:
    redis = await get_redis()
    data = await redis.get(driver_location_key(driver_id))
    return json.loads(data) if data else None


async def publish_location_update(order_id: str, message: dict[str, Any]) -> None:
    """Publish to Redis pub/sub channel for WebSocket broadcast."""
    redis = await get_redis()
    await redis.publish(order_tracking_channel(order_id), json.dumps(message, default=str))
