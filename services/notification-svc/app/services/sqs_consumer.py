"""SQS long-polling consumer for domain events with exponential backoff retry."""
import asyncio
import json
from typing import Any

import boto3
import structlog

from app.config import get_settings
from app.db.base import AsyncSessionLocal
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


async def poll_sqs() -> None:
    """Continuously poll SQS for messages."""
    global _running
    if not settings.SQS_QUEUE_URL_NOTIFICATION:
        logger.info("sqs_disabled_no_queue_url")
        return

    sqs = get_sqs()
    _running = True
    logger.info("sqs_consumer_started", queue=settings.SQS_QUEUE_URL_NOTIFICATION)

    while _running:
        try:
            response = sqs.receive_message(
                QueueUrl=settings.SQS_QUEUE_URL_NOTIFICATION,
                MaxNumberOfMessages=settings.SQS_MAX_MESSAGES,
                WaitTimeSeconds=settings.SQS_WAIT_TIME_SECONDS,
                VisibilityTimeout=settings.SQS_VISIBILITY_TIMEOUT,
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
                        sqs.delete_message(
                            QueueUrl=settings.SQS_QUEUE_URL_NOTIFICATION,
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
