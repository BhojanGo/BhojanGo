import json
from typing import Any

import structlog

from shared.config import get_settings
from shared.redis import close_redis, get_redis  # noqa: F401  (re-exported for app code)

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── Driver location keys ──────────────────────────────────────────────────────

def driver_location_key(driver_id: str) -> str:
    return f"driver:{driver_id}:location"


def order_tracking_channel(order_id: str) -> str:
    return f"tracking:{order_id}"


async def store_driver_location(driver_id: str, location: dict[str, Any]) -> None:
    redis = await get_redis()
    await redis.setex(
        driver_location_key(driver_id),
        settings.realtime.DRIVER_LOCATION_TTL,
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
