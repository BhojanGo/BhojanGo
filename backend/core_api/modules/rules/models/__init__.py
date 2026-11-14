"""Rules and their approvals (spec section 5: rules, rule_approvals).

A rule's versions share ``rule_key``. A published version is never edited;
changing it means a new draft version with its own ``effective_from``. When
that version is published, the previous one gets ``effective_to`` = the new
start, so exactly one version is active at any moment.

Statuses: draft -> pending_approval -> published | rejected.
Business rules skip pending_approval (no money involved); money rules need a
second admin (maker-checker).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_rules_key_version"),
        Index("ix_rules_lookup", "status", "scope_level", "scope_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    family: Mapped[str] = mapped_column(String(20), nullable=False)
    template: Mapped[str] = mapped_column(String(30), nullable=False)
    key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    slot: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope_level: Mapped[str] = mapped_column(String(12), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Market code that owns the rule (zone and restaurant rules: their city),
    # used for admin permissions and lists.
    market_scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # B4: an admin paused it (a kitchen's own offer, without ending it); the resolver skips it.
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    paused_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RuleApproval(Base):
    """Maker-checker trail: who asked, who decided, what they said."""

    __tablename__ = "rule_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(10), nullable=True)  # approved | rejected
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TierChange(Base):
    """A restaurant's tier (A/B/C) sets its commission and tier-based fees, so a change
    is asked for by one admin and approved by another (like a money rule)."""

    __tablename__ = "restaurant_tier_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_tier: Mapped[str | None] = mapped_column(String(1), nullable=True)
    to_tier: Mapped[str] = mapped_column(String(1), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # the restaurant's city code (who may approve)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")  # pending | approved | rejected
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["Rule", "RuleApproval", "TierChange"]
