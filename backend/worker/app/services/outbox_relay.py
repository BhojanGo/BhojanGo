"""Outbox relay (P11): publish committed outbox rows to SNS, oldest first.

Rows are claimed with FOR UPDATE SKIP LOCKED, so several workers can run it.
SNS fans out to the SQS queues (notifications, orders, delivery); with
EVENT_BUS=redis it's one Redis stream instead (shared/bus.py). A failed
publish is retried with the next batch; after MAX_ATTEMPTS it stops being
picked so one bad row can't block the rest (it stays visible for ops).
"""
import asyncio
import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from shared import bus
from shared.config import get_settings
from shared.db import AsyncSessionLocal
from shared.events import get_sns_client
from shared.outbox import OutboxEvent, topic_setting

logger = structlog.get_logger(__name__)

BATCH = 50
IDLE_SECONDS = 1.0
MAX_ATTEMPTS = 10

_running = False


def _topic_arn(event_type: str) -> str:
    s = get_settings()
    name = topic_setting(event_type)
    for section in (s.orders, s.payments, s.realtime):
        value = getattr(section, name, "")
        if value:
            return value
    return ""


def _publish(event: OutboxEvent) -> None:
    if bus.is_redis():
        bus.publish(event.envelope)
        return
    arn = _topic_arn(event.event_type)
    if not arn:
        raise RuntimeError(f"No SNS topic configured for {event.event_type}")
    get_sns_client().publish(
        TopicArn=arn,
        Message=json.dumps(event.envelope),
        Subject=event.event_type[:100],
        MessageAttributes={"event_type": {"DataType": "String", "StringValue": event.event_type}},
    )


async def relay_once(publish=_publish) -> int:  # type: ignore[no-untyped-def]
    """Publish one batch. Returns how many rows were published."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None), OutboxEvent.attempts < MAX_ATTEMPTS)
            .order_by(OutboxEvent.created_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        )).scalars().all()
        published = 0
        for row in rows:
            try:
                await asyncio.to_thread(publish, row)
                row.published_at = datetime.now(UTC)
                published += 1
            except Exception as e:  # noqa: BLE001 - keep the rest of the batch moving
                row.attempts += 1
                row.last_error = str(e)[:500]
                logger.warning("outbox_publish_failed", event_type=row.event_type, attempts=row.attempts, error=str(e))
        await db.commit()
        if published:
            logger.info("outbox_published", count=published)
        return published


async def run_relay() -> None:
    global _running
    _running = True
    logger.info("outbox_relay_started")
    while _running:
        try:
            n = await relay_once()
        except Exception as e:  # noqa: BLE001 - database blips: try again shortly
            logger.error("outbox_relay_error", error=str(e))
            n = 0
        if n < BATCH:
            await asyncio.sleep(IDLE_SECONDS)


def stop_relay() -> None:
    global _running
    _running = False
