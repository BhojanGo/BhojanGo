"""Saved cards: only the provider's token and what the customer needs to
recognise the card (brand, last four, expiry). Never a card number: the card
is entered in the provider's own form (Stripe Elements, Razorpay Checkout),
which hands us the token."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    __table_args__ = (
        CheckConstraint("provider IN ('stripe', 'razorpay', 'fake')", name="ck_payment_methods_provider"),
        CheckConstraint("length(last4) = 4", name="ck_payment_methods_last4"),
        CheckConstraint("exp_month BETWEEN 1 AND 12", name="ck_payment_methods_exp_month"),
        UniqueConstraint("user_id", "provider", "provider_token", name="uq_payment_methods_token"),
        Index("uq_payment_methods_one_default", "user_id", unique=True,
              postgresql_where=text("is_default"), sqlite_where=text("is_default")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(10), nullable=False)  # stripe | razorpay | fake
    provider_token: Mapped[str] = mapped_column(String(255), nullable=False)  # never returned by the API
    brand: Mapped[str] = mapped_column(String(20), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    exp_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
