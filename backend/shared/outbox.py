"""Transactional outbox (P11).

Modules never publish events straight to SNS: they add a row here in the same
database transaction as the change itself, so an event is published if and
only if the change committed. The worker relays unpublished rows to SNS (which
fans out to the SQS queues) and marks them published; a crash in between just
means the row is sent again (consumers dedupe by ``event_id``).
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base
from shared.events import build_event


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "created_at", postgresql_where="published_at IS NULL"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    envelope: Mapped[dict] = mapped_column(JSONB, nullable=False)  # what consumers receive
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


async def add(db: AsyncSession, event_type: str, aggregate_type: str, aggregate_id: str | uuid.UUID,
              payload: dict[str, Any], source: str) -> OutboxEvent:
    """Record an event to publish once this transaction commits."""
    row = OutboxEvent(
        event_type=event_type, aggregate_type=aggregate_type, aggregate_id=str(aggregate_id),
        envelope=build_event(event_type, payload, source),
    )
    db.add(row)
    await db.flush()
    return row


def topic_setting(event_type: str) -> str:
    """Which SNS topic setting an event goes to (order.* / payment.* / ...)."""
    family = event_type.split(".", 1)[0]
    return {"order": "SNS_TOPIC_ARN_ORDER", "payment": "SNS_TOPIC_ARN_PAYMENT", "delivery": "SNS_TOPIC_ARN_DELIVERY",
            "driver": "SNS_TOPIC_ARN_DELIVERY"}.get(family, "SNS_TOPIC_ARN_ORDER")
