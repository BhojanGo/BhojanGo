import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base


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
    minimum_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)

    # ── Pain-Point Layer: restaurant-friendly commission model ────────────────
    # pricing_model: percentage_commission | flat_fee_per_order | monthly_subscription
    pricing_model: Mapped[str] = mapped_column(String(30), nullable=False, default="percentage_commission")
    flat_fee_per_order: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    monthly_subscription_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))

    # ── Pain-Point Layer: hyper-local delivery radius & readiness ─────────────
    delivery_radius_km: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("5.00"))
    # R32: the restaurant takes pickup orders (it turns this on and off in its app)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    avg_prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # Market
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Tags
    tags: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Commission / delivery tier used by the rule engine (A, B, C); None = the rule's default.
    tier: Mapped[str | None] = mapped_column(String(1), nullable=True)

    # India: FSSAI food licence. The listing pauses itself when it expires (P10).
    fssai_number: Mapped[str | None] = mapped_column(String(14), nullable=True)
    fssai_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Why the listing is hidden from customers (e.g. fssai_expired); None = listed.
    paused_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # P19 partner tablet: "Pause orders" (is_open=False) ends by itself at paused_until (None = until resumed);
    # "Busy? Add 10 min" adds busy_extra_minutes to the prep time until busy_until.
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    busy_extra_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    busy_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # R17: paused by an admin (incident tools): customers see "Closed for now"; the kitchen can't undo it
    # from its tablet. Ends at admin_paused_until ("back at"), or when an admin resumes it.
    admin_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_paused_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)  # India: GST registration
    fssai_document_key: Mapped[str | None] = mapped_column(String(300), nullable=True)  # uploaded licence (P19)
    # R39: US food permit (in Idaho the health district's food establishment permit), where the country's
    # Markets setting food_permit_required is on: number, expiry, the uploaded permit and an admin's review.
    # Reminded 30 days before it expires; an expired one pauses the listing (paused_reason food_permit_expired).
    food_permit_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    food_permit_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    food_permit_document_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    food_permit_status: Mapped[str | None] = mapped_column(String(12), nullable=True)  # pending | approved | rejected
    food_permit_note: Mapped[str | None] = mapped_column(String(300), nullable=True)  # why it was rejected
    food_permit_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    food_permit_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    food_permit_reminded_for: Mapped[date | None] = mapped_column(Date, nullable=True)  # the expiry last reminded about

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_approval", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    @property
    def closed_for_now(self) -> bool:
        """R17: an admin paused it and the "back at" time (if any) hasn't come yet."""
        from datetime import UTC

        until = self.admin_paused_until
        return self.admin_paused_at is not None and (until is None or until > datetime.now(UTC))

    @property
    def back_at(self) -> datetime | None:
        return self.admin_paused_until if self.closed_for_now else None
