"""SNS event publisher for order domain events."""
import json
import uuid
from datetime import UTC, datetime

import boto3
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_sns_client = None


def get_sns_client():  # type: ignore[no-untyped-def]
    global _sns_client
    if _sns_client is None:
        kwargs: dict = {"region_name": settings.AWS_REGION}
        if settings.AWS_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
        if settings.AWS_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _sns_client = boto3.client("sns", **kwargs)
    return _sns_client


def _build_event(event_type: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_version": "1.0",
        "event_type": event_type,
        "source_service": "order-svc",
        "correlation_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }


async def publish_order_event(event_type: str, payload: dict) -> None:
    if not settings.SNS_TOPIC_ARN_ORDER:
        logger.debug("sns_disabled_skipping_publish", event_type=event_type)
        return

    event = _build_event(event_type, payload)
    try:
        sns = get_sns_client()
        sns.publish(
            TopicArn=settings.SNS_TOPIC_ARN_ORDER,
            Message=json.dumps(event),
            Subject=event_type,
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": event_type},
                "source_service": {"DataType": "String", "StringValue": "order-svc"},
            },
        )
        logger.info("event_published", event_type=event_type, event_id=event["event_id"])
    except Exception as e:
        logger.error("event_publish_failed", event_type=event_type, error=str(e))
