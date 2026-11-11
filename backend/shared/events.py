"""SNS client and domain-event envelope shared by modules that publish events.

Merged from order-svc and payment-svc core/events.py. The envelope fields are
unchanged; each module still passes its old ``source_service`` value so
consumers see exactly the same events as before.
"""
import uuid
from datetime import UTC, datetime

import boto3

from shared.config import get_settings
from shared.middleware.correlation import request_id_var

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


def build_event(event_type: str, payload: dict, source_service: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_version": "1.0",
        "event_type": event_type,
        "source_service": source_service,
        # Propagate the inbound request id so a trace survives across service boundaries.
        "correlation_id": request_id_var.get() or str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
