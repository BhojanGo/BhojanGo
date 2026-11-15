"""The signed-in account area (web): favourites and notification preferences.

Both are personal data: they go out in the data export and are removed when
the account is deleted.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class Favourite(Base):
    """A kitchen or a dish the customer saved. ``target_id`` points at a
    restaurant or a menu item (no FK: catalog rows are soft-deleted, and a
    favourite of something gone is simply not shown)."""

    __tablename__ = "favourites"
    __table_args__ = (CheckConstraint("kind IN ('restaurant', 'item')", name="ck_favourites_kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)  # restaurant | item
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationPreference(Base):
    """One switch: (category, channel) on or off. Only switches the customer
    has set are stored; the rest use the defaults in service/preferences.py."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint("category IN ('orders', 'offers', 'account')", name="ck_notification_preferences_category"),
        CheckConstraint("channel IN ('push', 'sms', 'email')", name="ck_notification_preferences_channel"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(10), primary_key=True)
    channel: Mapped[str] = mapped_column(String(10), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
