"""DynamoDB for delivery history (append-only log)."""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_dynamodb = None


def get_dynamodb():  # type: ignore[no-untyped-def]
    global _dynamodb
    if _dynamodb is None:
        kwargs: dict = {"region_name": settings.AWS_REGION}
        endpoint = settings.DYNAMODB_ENDPOINT_URL or settings.AWS_ENDPOINT_URL
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        _dynamodb = boto3.resource("dynamodb", **kwargs)
    return _dynamodb


async def record_location_event(
    order_id: str,
    driver_id: str,
    lat: float,
    lng: float,
    event_type: str = "location_update",
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        table = get_dynamodb().Table(settings.DYNAMODB_TABLE_DELIVERY_HISTORY)
        table.put_item(
            Item={
                "pk": order_id,
                "sk": f"{datetime.now(UTC).isoformat()}#{str(uuid.uuid4())[:8]}",
                "driver_id": driver_id,
                "lat": str(lat),
                "lng": str(lng),
                "event_type": event_type,
                "metadata": json.dumps(metadata or {}),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as e:
        logger.warning("dynamodb_write_failed", error=str(e))
