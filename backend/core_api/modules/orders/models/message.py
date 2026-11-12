"""Quick messages between the customer and the rider during an active order (B2).

Only the order's customer and its assigned rider write and read them, only
while the order is on its way (a rider assigned, not yet delivered or
cancelled). Nobody sees a phone number: people are shown by first name and
digits that look like a phone number are hidden in free text.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class OrderMessage(Base):
    __tablename__ = "order_messages"
    __table_args__ = (Index("ix_order_messages_order", "order_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(10), nullable=False)  # customer | rider
    preset: Mapped[str | None] = mapped_column(String(30), nullable=True)  # a quick message's key
    text: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False)
