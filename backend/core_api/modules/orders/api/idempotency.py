import json
import uuid
from typing import Any

from fastapi import Header, HTTPException, status
from redis.asyncio import Redis


async def validate_idempotency_key(
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
) -> str:
    """Validate that the idempotency key is a valid UUID."""
    try:
        uuid.UUID(x_idempotency_key, version=4)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Idempotency-Key must be a valid UUID v4",
        )
    return x_idempotency_key


async def check_idempotency(redis: Redis, service: str, key: str) -> dict | None:
    """Check if we already processed this idempotency key. Returns cached response or None."""
    cached = await redis.get(f"idempotency:{service}:{key}")
    if cached:
        return json.loads(cached)
    return None


async def store_idempotency(redis: Redis, service: str, key: str, response: dict) -> None:
    """Store the response for an idempotency key with 24h TTL."""
    await redis.setex(
        f"idempotency:{service}:{key}",
        86400,  # 24 hours
        json.dumps(response, default=str),
    )
