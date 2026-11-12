import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Float, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


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
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_payment", index=True)

    # Where the order is (from its quote): admin scopes and the business rules.
    market_city: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # P11 lifecycle: deadlines the timeout sweeper enforces, and when each step happened.
    payment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accept_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rider_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # P18: the customer gives the rider this PIN at the door; the proof the rider gave.
    delivery_pin: Mapped[str | None] = mapped_column(String(4), nullable=True)
    delivery_proof: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Dispatch and tracking (P14): the restaurant and the delivery point.
    pickup_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    pickup_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(20), nullable=True)  # customer | restaurant | admin | system

    # Financials (stored as NUMERIC for exact money arithmetic; denominated in major units, e.g. dollars/rupees)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    taxes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    tip: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # ── Pain-Point Layer: commission / fee transparency ───────────────────────
    # platform_fee = platform revenue from the restaurant for this order (commission model);
    # restaurant_payout = subtotal - platform_fee. Neither changes the customer's total.
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    restaurant_payout: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))

    # ── Pain-Point Layer: restaurant readiness / predictive dispatch ──────────
    estimated_prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    restaurant_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Pain-Point Layer: hyper-local delivery distance ───────────────────────
    delivery_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_long_distance: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ── Pain-Point Layer: customer transparency timeline ──────────────────────
    # List of {"status": str, "at": iso8601} appended on every state transition.
    status_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

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
