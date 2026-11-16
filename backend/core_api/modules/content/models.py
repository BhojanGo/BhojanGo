"""Content managed in the admin console (round 8, F9): the Help centre.

A help article is one slug in one language for one country, or for every
country ("*"). The website asks for the visitor's country and language and
falls back: that country in that language, that country in English, every
country in that language, every country in English (service/help.py).

Columns hold what the public sees once the article is published. Edits to a
published article wait in ``draft`` until someone publishes them, so the live
page never shows half-finished text. Every save, publish and unpublish adds a
row to help_article_versions (the content as it was) and to the audit log (who
and when).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base

GLOBAL = "*"
TOPICS = ("orders", "payments-refunds", "delivery", "account", "kitchen-partners", "delivery-partners")
LANGUAGES = ("en", "hi", "te", "ta", "kn", "mr", "bn", "es")


class HelpArticle(Base):
    __tablename__ = "help_articles"
    __table_args__ = (UniqueConstraint("slug", "country", "language", name="uq_help_articles_slug_country_language"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(30), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default=GLOBAL)  # "IN", "US" or "*"
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")  # Markdown (a small subset)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")  # draft | published
    popular: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0: not popular; 1.. their order
    related: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # slugs
    # Unpublished changes to a published article: {title, summary, body, topic, popular, related}
    draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Who last changed it in the console (NULL: only ever loaded by the seed, which may refresh it).
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class HelpArticleVersion(Base):
    """The article as it was after each change: what the console's History shows."""

    __tablename__ = "help_article_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("help_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # created | edited | published | unpublished
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)  # title, summary, body, topic, popular, related
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class HelpVote(Base):
    """"Was this helpful?": one vote per article per visitor (a random id the
    browser keeps, hashed), which they may change. Anonymous."""

    __tablename__ = "help_votes"
    __table_args__ = (UniqueConstraint("article_id", "voter", name="uq_help_votes_article_voter"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("help_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    voter: Mapped[str] = mapped_column(String(64), nullable=False)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


__all__ = ["GLOBAL", "LANGUAGES", "TOPICS", "HelpArticle", "HelpArticleVersion", "HelpVote"]
