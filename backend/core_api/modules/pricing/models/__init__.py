"""Pricing records (spec section 5: order_pricing_snapshot)."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class OrderPricingSnapshot(Base):
    """What an order was charged and why: every bill line, the rule versions
    that priced it, and who gets what. Never changes after the order is placed."""

    __tablename__ = "order_pricing_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    lines: Mapped[list] = mapped_column(JSONB, nullable=False)
    rule_versions: Mapped[list] = mapped_column(JSONB, nullable=False)
    split: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)  # zone, city, distance, local time
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PromotionSpend(Base):
    """Running total given away per promotion (rule_key), for budget caps."""

    __tablename__ = "promotion_spend"

    rule_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    orders: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


__all__ = ["OrderPricingSnapshot", "PromotionSpend"]


class PromotionSpendWeek(Base):
    """Given away per promotion per week (Monday, market time), for weekly caps on
    offers a restaurant funds (P19)."""

    __tablename__ = "promotion_spend_week"

    rule_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    orders: Mapped[int] = mapped_column(nullable=False, default=0)
