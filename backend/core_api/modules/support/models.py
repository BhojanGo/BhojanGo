"""Support tickets (B3, B5): what someone asked us to deal with.

- callback: a kitchen asks us to call it back (partner tablet, Help).
- problem: a customer reported a problem with an order above what we refund
  automatically (B5).

Tickets show in the admin support console for the city; whoever deals with one
resolves it with a note (audited).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (Index("ix_support_tickets_open", "status", "market_city", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # callback | problem
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")  # open | resolved
    market_city: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    requester_role: Mapped[str] = mapped_column(String(20), nullable=False)  # partner | customer
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(500), nullable=True)
