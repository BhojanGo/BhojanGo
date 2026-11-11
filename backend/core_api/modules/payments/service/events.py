"""SNS event publisher for payment events.

The SNS client and envelope are shared (shared.events). The message, subject
and attributes are exactly what payment-svc published, including
source_service="payment-svc" and only the event_type message attribute.
"""
import asyncio
import json

import structlog

from shared.config import get_settings
from shared.events import build_event, get_sns_client

logger = structlog.get_logger(__name__)
settings = get_settings()

SOURCE_SERVICE = "payment-svc"


async def publish_payment_event(event_type: str, payload: dict) -> None:
    if not settings.payments.SNS_TOPIC_ARN_PAYMENT:
        logger.debug("sns_disabled", event_type=event_type)
        return
    event = build_event(event_type, payload, SOURCE_SERVICE)
    try:
        await asyncio.to_thread(
            get_sns_client().publish,
            TopicArn=settings.payments.SNS_TOPIC_ARN_PAYMENT,
            Message=json.dumps(event),
            Subject=event_type,
            MessageAttributes={"event_type": {"DataType": "String", "StringValue": event_type}},
        )
        logger.info("payment_event_published", event_type=event_type)
    except Exception as e:
        logger.error("payment_event_failed", event_type=event_type, error=str(e))
