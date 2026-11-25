import uuid
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, Time, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # R43: served only between these local times (both set; until <= from runs past midnight), e.g. breakfast 07:00-11:00
    available_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    available_until: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="categories")  # type: ignore[name-defined]  # noqa: F821
    items: Mapped[list["MenuItem"]] = relationship("MenuItem", back_populates="category_obj")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    is_veg: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_vegan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    allergens: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    # Option groups (size, spice, add-ons) live in catalog/models/options.py (P10).
    # "Sold out today": hidden from ordering until this time (the restaurant's next local midnight).
    sold_out_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prep_time_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # R43: 0 none, 1 mild, 2 medium, 3 hot (None: not said); a schedule like the category's
    spice_level: Mapped[int | None] = mapped_column(SmallInteger, CheckConstraint("spice_level BETWEEN 0 AND 3", name="ck_menu_items_spice_level"), nullable=True)
    available_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    available_until: Mapped[time | None] = mapped_column(Time, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="menu_items")  # type: ignore[name-defined]  # noqa: F821
    category_obj: Mapped["MenuCategory"] = relationship("MenuCategory", back_populates="items")


class MenuChange(Base):
    """R43: the menu's history. One row per change a restaurant or an admin made: who, when, and each
    field's old and new value ({"field", "old", "new"}). Never updated or deleted by the app."""

    __tablename__ = "menu_changes"
    __table_args__ = (Index("ix_menu_changes_restaurant_at", "restaurant_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    actor_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # restaurant | admin
    entity: Mapped[str] = mapped_column(String(20), nullable=False)  # dish | category | options | menu
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # added | changed | deleted | reordered
    changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
