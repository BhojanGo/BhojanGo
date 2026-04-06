import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    restaurant_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    driver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Items stored as JSONB list
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # State machine
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)

    # Financials
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    taxes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tip: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Delivery
    delivery_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estimated_delivery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Payment
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Cancellation
    cancellation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancellation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extras
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    promo_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    loyalty_points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loyalty_points_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
