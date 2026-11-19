"""Incident tools (R17): what admin uses when something breaks (docs/launch/incident-plan.md).

- ``OrderingPause``: new orders stop for a city, a country or everywhere ("*") until it is ended
  or its end time passes; customers see a message on the website and in the app. Orders already
  placed carry on.
- ``BulkRefund``: many orders refunded at once (a kitchen's, a zone's or a city's in a time window),
  full or a percentage; above the city's auto-refund limit a second admin approves it first.
- ``BulkMessage``: one incident message (a template from the incident plan) to many customers by
  push and email, each in their own language.

A kitchen paused by an admin lives on the restaurant (``admin_paused_*``): the kitchen can't undo it
from its tablet. Every action writes an audit entry (entity types ``restaurant``, ``ordering_pause``,
``bulk_refund``, ``bulk_message``).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class OrderingPause(Base):
    __tablename__ = "ordering_pauses"
    __table_args__ = (Index("ix_ordering_pauses_active", "ended_at", "scope"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # "*" | "IN" | "IN-TG-HYD"
    area: Mapped[str] = mapped_column(String(100), nullable=False)  # the name customers see ("Hyderabad")
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # admins only
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)  # shown to customers as written
    until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # None: until ended
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BulkRefund(Base):
    __tablename__ = "bulk_refunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_city: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)  # restaurant_id / zone_id / placed_from / placed_to
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # full | percent
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    orders: Mapped[list] = mapped_column(JSONB, nullable=False)  # [{order_id, amount (minor), customer_id, ...}]
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)  # minor units
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # pending_approval | done | partly_failed | rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{order_id, ok, amount, error}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BulkMessage(Base):
    __tablename__ = "bulk_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # the city the customers are in
    audience: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {"bulk_refund_id": ...} | {"city": ..., "days": 30}
    template: Mapped[str] = mapped_column(String(40), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recipients: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False)  # outside production: real (not test) accounts
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
