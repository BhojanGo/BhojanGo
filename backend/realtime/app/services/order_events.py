"""Order events for realtime (P14): the order topic fans out to an SQS queue;
realtime reads it to start dispatch and to push status changes to trackers.
A loop also expires rider offers and retries orders waiting for a rider."""
import asyncio
import json

import boto3
import structlog

from app.services import dispatch
from shared.config import get_settings

logger = structlog.get_logger(__name__)
_running = False


def _sqs():  # type: ignore[no-untyped-def]
    s = get_settings()
    kwargs: dict = {"region_name": s.AWS_REGION}
    if s.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = s.AWS_ENDPOINT_URL
    return boto3.client("sqs", **kwargs)


def parse(body: str) -> dict:
    data = json.loads(body)
    return json.loads(data["Message"]) if "Message" in data else data  # SNS envelope


async def consume() -> None:
    url = get_settings().realtime.SQS_QUEUE_URL_ORDERS
    if not url:
        logger.info("order_events_disabled_no_queue")
        return
    sqs = _sqs()
    logger.info("order_events_consumer_started", queue=url)
    while _running:
        try:
            resp = await asyncio.to_thread(sqs.receive_message, QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=10)
            for msg in resp.get("Messages", []):
                try:
                    await dispatch.on_order_event(parse(msg["Body"]))
                    await asyncio.to_thread(sqs.delete_message, QueueUrl=url, ReceiptHandle=msg["ReceiptHandle"])
                except Exception as e:  # noqa: BLE001 - left on the queue; retried, then the DLQ
                    logger.error("order_event_failed", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.error("order_events_poll_error", error=str(e))
            await asyncio.sleep(5)


async def ticker() -> None:
    while _running:
        try:
            await dispatch.tick()
        except Exception as e:  # noqa: BLE001
            logger.error("dispatch_tick_failed", error=str(e))
        await asyncio.sleep(1)


def start() -> list[asyncio.Task]:
    global _running
    _running = True
    return [asyncio.create_task(consume()), asyncio.create_task(ticker())]


def stop() -> None:
    global _running
    _running = False
