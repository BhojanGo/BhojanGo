"""Ask the worker to send an SMS or email (``notify.send`` on the notification queue).

core_api never talks to SMS or email providers itself: it puts a message on
the notification SQS queue (LocalStack locally) and the worker sends it with
its configured provider. Locally that means OTP codes show up in the worker
log and emails in Mailpit. With no queue configured (unit tests), the message
is sent in-process with the same providers.
"""
import asyncio
import json
from typing import Literal

import boto3
import structlog

from shared.config import get_settings
from shared.events import build_event

logger = structlog.get_logger(__name__)

Channel = Literal["sms", "email"]
EVENT_TYPE = "notify.send"

_sqs = None


def _sqs_client():  # type: ignore[no-untyped-def]
    global _sqs
    if _sqs is None:
        s = get_settings()
        kwargs: dict = {"region_name": s.AWS_REGION}
        if s.AWS_ENDPOINT_URL:
            kwargs["endpoint_url"] = s.AWS_ENDPOINT_URL
        _sqs = boto3.client("sqs", **kwargs)
    return _sqs


async def deliver(payload: dict) -> bool:
    """Send one notify.send payload with the configured provider (the worker calls this)."""
    from shared.providers.email import get_email_provider
    from shared.providers.sms import get_sms_provider

    if payload["channel"] == "sms":
        country = payload.get("country", "US")
        return await get_sms_provider(country).send(
            payload["to"], payload["body"], country, payload.get("template", ""), payload.get("params") or {}
        )
    if payload["channel"] == "email":
        return await get_email_provider().send(payload["to"], payload["subject"], payload["body"])
    logger.warning("notify_unknown_channel", channel=payload.get("channel"))
    return False


async def send(
    channel: Channel, to: str, body: str, *, subject: str = "", country: str = "US",
    template: str = "", params: dict | None = None,
) -> bool:
    """``template``/``params``: the DLT template key and variables (India SMS)."""
    payload = {"channel": channel, "to": to, "body": body, "subject": subject, "country": country,
               "template": template, "params": params or {}}
    from shared import bus

    if bus.is_redis():
        try:
            await asyncio.to_thread(bus.publish, build_event(EVENT_TYPE, payload, get_settings().SERVICE_NAME))
            logger.info("notify_queued", channel=channel, to=to[-4:])
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("notify_queue_failed", channel=channel, error=str(e))
            return False
    queue_url = get_settings().worker.SQS_QUEUE_URL_NOTIFICATION
    if not queue_url:
        return await deliver(payload)
    event = build_event(EVENT_TYPE, payload, get_settings().SERVICE_NAME)
    try:
        await asyncio.to_thread(_sqs_client().send_message, QueueUrl=queue_url, MessageBody=json.dumps(event))
        logger.info("notify_queued", channel=channel, to=to[-4:])
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("notify_queue_failed", channel=channel, error=str(e))
        return False
