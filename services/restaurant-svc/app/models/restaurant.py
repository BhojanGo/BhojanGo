import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cuisine_types: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Address + Location stored as JSONB
    address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # lat/lng stored separately for indexing (PostGIS in production)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Metrics
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Operations
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opens_at: Mapped[str | None] = mapped_column(String(5), nullable=True)   # HH:MM
    closes_at: Mapped[str | None] = mapped_column(String(5), nullable=True)
    delivery_time_min: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    delivery_time_max: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    minimum_order_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Market
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Tags
    tags: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    menu_items: Mapped[list["MenuItem"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "MenuItem", back_populates="restaurant", cascade="all, delete-orphan"
    )
    categories: Mapped[list["MenuCategory"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "MenuCategory", back_populates="restaurant", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Review", back_populates="restaurant", cascade="all, delete-orphan"
    )
