"""Payout accounts, weekly payout runs and statements (P13)."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false, func
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
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")  # pending | active | restricted
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # What the provider says (R10; Stripe: account.updated and on demand). status is
    # "active" exactly when payouts_enabled; service/connect.py turns these into the
    # state people see (not started, in progress, action needed, ready).
    details_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    requirements_due: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    disabled_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payout_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # the last bank payout that failed (payout.failed)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PayoutRun(Base):
    """One country's payouts for one period. draft -> approved -> paid."""

    __tablename__ = "payout_runs"
    __table_args__ = (
        UniqueConstraint("country", "period_start", "period_end", name="uq_payout_runs_period"),
        # R41: a run is one week, Monday (in the country's payout zone) to the next Monday (migration 0054: NOT VALID,
        # so rows made before it are listed, not changed)
        CheckConstraint("extract(isodow from period_start) = 1 AND period_end = period_start + 7", name="ck_payout_runs_monday_week"),
    )

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
    __table_args__ = (Index("ix_payout_statements_payee", "payee_type", "payee_id"),
                      Index("ix_payout_statements_carried_to", "carried_to"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payee_type: Mapped[str] = mapped_column(String(12), nullable=False)
    payee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payee_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # minor units
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    lines: Mapped[list] = mapped_column(JSONB, nullable=False)
    # pending | paid | failed | no_account | onboarding (account not ready yet) | reversed
    # | carried (R23: below zero; nothing sent, the balance moves to the payee's next statement)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    transfer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Transfers tried: the idempotency key is "<run>:<statement>:<attempts>", so a retry
    # after a definite failure or a reversal is a new transfer, and a timed-out one isn't.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # R23, a kitchen's week below zero: never written off, never charged to the kitchen. ``amount``
    # is the week's net plus ``carried_in`` (minor units, <= 0: what earlier statements left below
    # zero, "Carried from last week"). A statement whose amount is below zero pays nothing and is
    # carried into the next run's statement, which it then names in ``carried_to`` (set once, so a
    # balance is never carried twice). ``negative_weeks`` counts the payee's weeks below zero in a
    # row, this one included (0 when it isn't), since the Monday ``negative_since``; from 4 weeks
    # admin Finance lists the kitchen to collect from (service/payouts.py, to_collect).
    carried_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    carried_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    negative_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    negative_since: Mapped[date | None] = mapped_column(Date, nullable=True)


class PayoutRunOrder(Base):
    """R41: an order belongs to at most one payout run (the primary key). Written when a run is prepared; deleting a
    run releases its orders."""

    __tablename__ = "payout_run_orders"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payout_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["PayoutAccount", "PayoutRun", "PayoutRunOrder", "PayoutStatement"]
