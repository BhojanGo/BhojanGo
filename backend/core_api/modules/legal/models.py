"""Legal documents and who accepted which version (R8 F10).

LegalDocument: the Terms, the Privacy notice (and later the kitchen partner and
delivery partner terms) of one country in one language, versioned. A document is
written as a draft in the admin console (Content → Legal); publishing it gives it
the next version number for its kind, country and language and supersedes the
version before it, which stays readable in the version history.

LegalAcceptance: a person accepted a published version (at sign-up, or by
continuing past the "We updated our Terms" notice). Kept when an account is
deleted: it holds no personal details beyond the anonymous account id, and is
the evidence of what the person agreed to.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base

KINDS = ("terms", "privacy", "kitchen_partner_terms", "delivery_partner_terms")
STATUSES = ("draft", "published", "superseded")


class LegalDocument(Base):
    __tablename__ = "legal_documents"
    __table_args__ = (
        UniqueConstraint("kind", "country", "language", "version", name="uq_legal_documents_version"),
        Index("ix_legal_documents_lookup", "kind", "country", "language", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)  # set when published (1, 2, 3 ...)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")  # draft | published | superseded
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    key_points: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # short sentences
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")  # Markdown
    summary_of_changes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
                                                 nullable=False)


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", name="uq_legal_acceptances_user_document"),
        Index("ix_legal_acceptances_user_kind", "user_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False)  # web | app
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(160), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["KINDS", "STATUSES", "LegalAcceptance", "LegalDocument"]
