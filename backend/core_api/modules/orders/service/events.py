"""SNS event publisher for order domain events.

The SNS client and envelope are shared (shared.events). The message, subject
and attributes are exactly what order-svc published, including
source_service="order-svc", so consumers are unaffected.
"""
import json

import structlog

from shared.config import get_settings
from shared.events import build_event, get_sns_client

logger = structlog.get_logger(__name__)
settings = get_settings()

SOURCE_SERVICE = "order-svc"


async def publish_order_event(event_type: str, payload: dict) -> None:
    if not settings.orders.SNS_TOPIC_ARN_ORDER:
        logger.debug("sns_disabled_skipping_publish", event_type=event_type)
        return

    event = build_event(event_type, payload, SOURCE_SERVICE)
    try:
        sns = get_sns_client()
        sns.publish(
            TopicArn=settings.orders.SNS_TOPIC_ARN_ORDER,
            Message=json.dumps(event),
            Subject=event_type,
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": event_type},
                "source_service": {"DataType": "String", "StringValue": SOURCE_SERVICE},
            },
        )
        logger.info("event_published", event_type=event_type, event_id=event["event_id"])
    except Exception as e:
        logger.error("event_publish_failed", event_type=event_type, error=str(e))
