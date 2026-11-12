"""Payout accounts, weekly payout runs and statements (P13)."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class PayoutAccount(Base):
    """Where a restaurant or rider is paid: a Stripe Connect Express account,
    a Razorpay Route linked account, or a fake one locally."""

    __tablename__ = "payout_accounts"
    __table_args__ = (UniqueConstraint("payee_type", "payee_id", "provider", name="uq_payout_accounts_payee"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payee_type: Mapped[str] = mapped_column(String(12), nullable=False)  # restaurant | rider
    payee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")  # pending | active | restricted
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PayoutRun(Base):
    """One country's payouts for one period. draft -> approved -> paid."""

    __tablename__ = "payout_runs"
    __table_args__ = (UniqueConstraint("country", "period_start", "period_end", name="uq_payout_runs_period"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)  # local dates, end exclusive
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft | approved | partially_paid | paid
    totals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayoutStatement(Base):
    """What one payee earned in a run, line by line, and whether it was paid."""

    __tablename__ = "payout_statements"
    __table_args__ = (Index("ix_payout_statements_payee", "payee_type", "payee_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payee_type: Mapped[str] = mapped_column(String(12), nullable=False)
    payee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payee_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # minor units
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    lines: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | paid | failed | no_account
    transfer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["PayoutAccount", "PayoutRun", "PayoutStatement"]
