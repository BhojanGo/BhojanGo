"""Markets: countries, regions (states), cities and zones (docs/specs/01-structure.md, sections 2 and 5).

Every level has a ``code`` (``IN``, ``IN-TG``, ``IN-TG-HYD``) that doubles as the
admin scope (shared/authz.py), a status (draft, soon, beta, live, paused) and a
``settings`` JSON object whose keys inherit downwards: country -> region ->
city (the most specific level that sets a key wins).
"""
import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base

STATUSES = ("draft", "soon", "beta", "live", "paused")
PAYOUT_PROVIDERS = ("stripe_connect", "razorpay_route", "fake", "none")


class _Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Country(_Timestamps, Base):
    __tablename__ = "countries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)  # ISO 3166-1 alpha-2
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    locales: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    distance_unit: Mapped[str] = mapped_column(String(2), nullable=False, default="km")  # km | mi
    phone_code: Mapped[str] = mapped_column(String(5), nullable=False)
    payment_providers: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False)
    tax_regime: Mapped[str] = mapped_column(String(20), nullable=False)  # gst | us_sales_tax
    # Who pays restaurants and riders here (finance/service/providers.py): stripe_connect,
    # razorpay_route, fake (never in production) or none (the country can't open).
    payout_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="none", server_default="none")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")


class Region(_Timestamps, Base):
    """A state or province."""

    __tablename__ = "regions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)  # ISO 3166-2, e.g. IN-TG
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # The state's short code people write after a city ("Boise, ID", "Hyderabad, TG"): the location line on the
    # website and in the app. Required in admin; filled from the ISO code's second part when a state was made
    # without one (migration 0039 did that for the existing states).
    short_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)  # None = the country's
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")


def region_short_code(region: "Region") -> str:
    """The state's short code ("ID"): its own, else the second part of its ISO code ("US-ID" -> "ID")."""
    return (region.short_code or region.code.split("-", 1)[-1]).upper()


class City(_Timestamps, Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("countries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # IN-TG-HYD
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # {"open": "07:00", "close": "23:30"} in the city's local time
    service_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")


class Zone(_Timestamps, Base):
    """A delivery area: a polygon on the map with its own minimum order and status."""

    __tablename__ = "zones"
    __table_args__ = (
        UniqueConstraint("city_id", "name", name="uq_zones_city_name"),
        Index("ix_zones_polygon", "polygon", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    polygon: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    min_order: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#0B5D66")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = ["PAYOUT_PROVIDERS", "STATUSES", "City", "Country", "Region", "Zone"]


class LaunchWaitlist(Base):
    """"Notify me" sign-ups: a coming-soon city, an address outside every zone, or a
    city the visitor suggests. Markets shows the demand per city (admin)."""

    __tablename__ = "launch_waitlist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    city_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # a known city
    city_text: Mapped[str | None] = mapped_column(String(100), nullable=True)  # the visitor's own words
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="app")
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
