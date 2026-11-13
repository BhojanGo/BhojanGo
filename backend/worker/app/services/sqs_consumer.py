"""SQS long-polling consumer for domain events with exponential backoff retry."""
import asyncio
import json
from typing import Any

import boto3
import structlog

from shared import bus
from shared.config import get_settings
from shared.db import AsyncSessionLocal
from app.services.dispatcher import dispatch_event

logger = structlog.get_logger(__name__)
settings = get_settings()

_running = False


def get_sqs():  # type: ignore[no-untyped-def]
    kwargs: dict = {"region_name": settings.AWS_REGION}
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
    return boto3.client("sqs", **kwargs)


async def process_message(message: dict[str, Any]) -> None:
    """Parse and dispatch a single SQS message."""
    async with AsyncSessionLocal() as db:
        try:
            body = json.loads(message["Body"])
            # SNS wraps message in {"Message": "..."}
            if "Message" in body:
                event = json.loads(body["Message"])
            else:
                event = body

            await dispatch_event(event, db)
            await db.commit()
        except Exception as e:
            logger.error("message_processing_failed", error=str(e), message_id=message.get("MessageId"))
            await db.rollback()
            raise


async def handle_event(event: dict[str, Any]) -> None:
    """One event from the Redis bus (EVENT_BUS=redis): same handling as an SQS message."""
    async with AsyncSessionLocal() as db:
        try:
            await dispatch_event(event, db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def poll_sqs() -> None:
    """Continuously poll SQS for messages (or read the Redis bus)."""
    global _running
    if bus.is_redis():
        _running = True
        await bus.consume("worker", handle_event, running=lambda: _running)
        return
    if not settings.worker.SQS_QUEUE_URL_NOTIFICATION:
        logger.info("sqs_disabled_no_queue_url")
        return

    sqs = get_sqs()
    _running = True
    logger.info("sqs_consumer_started", queue=settings.worker.SQS_QUEUE_URL_NOTIFICATION)

    while _running:
        try:
            # boto3 is blocking: long-poll in a thread so the API (health checks) stays responsive.
            response = await asyncio.to_thread(
                sqs.receive_message,
                QueueUrl=settings.worker.SQS_QUEUE_URL_NOTIFICATION,
                MaxNumberOfMessages=settings.worker.SQS_MAX_MESSAGES,
                WaitTimeSeconds=settings.worker.SQS_WAIT_TIME_SECONDS,
                VisibilityTimeout=settings.worker.SQS_VISIBILITY_TIMEOUT,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            if not messages:
                continue

            for message in messages:
                receipt_handle = message["ReceiptHandle"]
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        await process_message(message)
                        # Delete only on success
                        await asyncio.to_thread(
                            sqs.delete_message,
                            QueueUrl=settings.worker.SQS_QUEUE_URL_NOTIFICATION,
                            ReceiptHandle=receipt_handle,
                        )
                        break
                    except Exception as e:
                        retry_count += 1
                        backoff = 2 ** retry_count
                        logger.warning(
                            "message_retry",
                            attempt=retry_count,
                            backoff=backoff,
                            error=str(e),
                        )
                        if retry_count < max_retries:
                            await asyncio.sleep(backoff)
                        else:
                            logger.error("message_dlq", message_id=message.get("MessageId"))
                            # Message goes to DLQ automatically after max receives

        except Exception as e:
            logger.error("sqs_poll_error", error=str(e))
            await asyncio.sleep(5)


def stop_polling() -> None:
    global _running
    _running = False
