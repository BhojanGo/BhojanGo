import json
import uuid
from datetime import UTC, datetime

import boto3
import structlog

from app.config import get_settings
from app.middleware.correlation import request_id_var

logger = structlog.get_logger(__name__)
settings = get_settings()
_sns = None


def get_sns():  # type: ignore[no-untyped-def]
    global _sns
    if _sns is None:
        kwargs: dict = {"region_name": settings.AWS_REGION}
        if settings.AWS_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
        _sns = boto3.client("sns", **kwargs)
    return _sns


async def publish_payment_event(event_type: str, payload: dict) -> None:
    if not settings.SNS_TOPIC_ARN_PAYMENT:
        logger.debug("sns_disabled", event_type=event_type)
        return
    event = {
        "event_id": str(uuid.uuid4()),
        "event_version": "1.0",
        "event_type": event_type,
        "source_service": "payment-svc",
        # Propagate the inbound request id so a trace survives across service boundaries.
        "correlation_id": request_id_var.get() or str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    try:
        get_sns().publish(
            TopicArn=settings.SNS_TOPIC_ARN_PAYMENT,
            Message=json.dumps(event),
            Subject=event_type,
            MessageAttributes={"event_type": {"DataType": "String", "StringValue": event_type}},
        )
        logger.info("payment_event_published", event_type=event_type)
    except Exception as e:
        logger.error("payment_event_failed", event_type=event_type, error=str(e))
