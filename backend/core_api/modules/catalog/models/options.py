"""Menu modifiers and store hours (P10).

Option groups belong to a restaurant and can be shared by several items
(e.g. one "Spice" group). A group says how many options the customer must and
may pick (min_picks / max_picks): Size is 1..1, Add-ons 0..3.

Store hours are weekly ranges in the restaurant's local time; a range may run
past midnight (22:00-02:00). An override replaces a day's hours (a holiday,
or open late for an event).
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class OptionGroup(Base):
    __tablename__ = "option_groups"
    __table_args__ = (CheckConstraint("min_picks >= 0 AND max_picks >= 1 AND min_picks <= max_picks", name="ck_option_groups_picks"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    min_picks: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_picks: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    options: Mapped[list["Option"]] = relationship(
        "Option", back_populates="group", cascade="all, delete-orphan", order_by="Option.sort_order", lazy="selectin"
    )


class Option(Base):
    __tablename__ = "options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("option_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    group: Mapped[OptionGroup] = relationship("OptionGroup", back_populates="options")


class MenuItemOptionGroup(Base):
    """Which groups an item offers, in display order."""

    __tablename__ = "menu_item_option_groups"

    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("option_groups.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StoreHours(Base):
    __tablename__ = "store_hours"
    __table_args__ = (CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_store_hours_weekday"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0 = Monday
    opens: Mapped[time] = mapped_column(Time, nullable=False)
    closes: Mapped[time] = mapped_column(Time, nullable=False)  # <= opens: runs past midnight


class StoreHoursOverride(Base):
    __tablename__ = "store_hour_overrides"
    __table_args__ = (UniqueConstraint("restaurant_id", "day", name="uq_store_hour_overrides_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)  # local date
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    opens: Mapped[time | None] = mapped_column(Time, nullable=True)
    closes: Mapped[time | None] = mapped_column(Time, nullable=True)
    note: Mapped[str | None] = mapped_column(String(120), nullable=True)


__all__ = ["MenuItemOptionGroup", "Option", "OptionGroup", "StoreHours", "StoreHoursOverride"]
