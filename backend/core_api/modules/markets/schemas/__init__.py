import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

Status = Literal["draft", "soon", "beta", "live", "paused"]
# Who pays restaurants and riders in a country. "fake" moves no money (never in
# production); "none" means payouts aren't set up, so the country can't open.
PayoutProviderName = Literal["stripe_connect", "razorpay_route", "fake", "none"]
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ServiceHours(BaseModel):
    open: str = Field(examples=["07:00"])
    close: str = Field(examples=["23:30"], description="May be after midnight, e.g. 01:00")

    @field_validator("open", "close")
    @classmethod
    def hhmm(cls, v: str) -> str:
        if not HHMM.match(v):
            raise ValueError("Use 24-hour HH:MM")
        return v


def _zone(v: str | None) -> str | None:
    """An IANA time zone name ("America/Boise"), or None."""
    if v is None:
        return None
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    v = v.strip()
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"{v!r} isn't a time zone; use an IANA name such as America/Boise or Asia/Kolkata")
    return v


# ── Countries ─────────────────────────────────────────────────────────────────

class CountryCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2}$", examples=["IN"])
    name: str = Field(min_length=2, max_length=100)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    locales: list[str] = Field(min_length=1, examples=[["en-IN", "hi-IN", "te-IN"]])
    timezone: str = Field(description="The zone a new city starts with (each city has its own)")
    payout_timezone: str | None = Field(default=None, description="Payout weeks are counted in this zone; none = timezone")
    distance_unit: Literal["km", "mi"] = "km"
    phone_code: str = Field(pattern=r"^\+\d{1,4}$")
    payment_providers: list[str] = Field(min_length=1)
    tax_regime: Literal["gst", "us_sales_tax"]
    payout_provider: PayoutProviderName = "none"
    settings: dict[str, Any] = {}

    _zones = field_validator("timezone", "payout_timezone")(classmethod(lambda cls, v: _zone(v)))


class CountryUpdate(BaseModel):
    name: str | None = None
    locales: list[str] | None = None
    timezone: str | None = None
    payout_timezone: str | None = None
    distance_unit: Literal["km", "mi"] | None = None
    payment_providers: list[str] | None = None
    tax_regime: Literal["gst", "us_sales_tax"] | None = None
    payout_provider: PayoutProviderName | None = None
    settings: dict[str, Any] | None = None
    status: Status | None = None

    _zones = field_validator("timezone", "payout_timezone")(classmethod(lambda cls, v: _zone(v)))


class CountryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    name: str
    currency: str
    locales: list[str]
    timezone: str
    payout_timezone: str | None = None
    distance_unit: str
    phone_code: str
    payment_providers: list[str]
    tax_regime: str
    payout_provider: PayoutProviderName
    settings: dict[str, Any]
    status: Status

    @computed_field  # type: ignore[prop-decorator]
    @property
    def payment_methods_supported(self) -> list[str]:
        """What the country's payment providers take (R14): admin offers only these."""
        from core_api.modules.markets.service.pay_methods import supported

        return supported(self.payment_providers)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def legal_missing(self) -> list[str]:
        """Legal entity fields still empty (R15): each is required before the country launches."""
        from core_api.modules.markets.service.legal import missing

        return missing(self.settings, self.tax_regime)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def payout_zone(self) -> str:
        """R27: the zone finance counts this country's weeks in (payout_timezone, else timezone)."""
        return self.payout_timezone or self.timezone


# ── Regions (states) ──────────────────────────────────────────────────────────

SHORT_CODE = r"^[A-Z0-9]{1,4}$"


class RegionCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}$", examples=["IN-TG"])
    name: str = Field(min_length=2, max_length=100)
    # What people write after a city ("Boise, ID"). Admin's form requires it; left out, the ISO code's second part.
    short_code: str | None = Field(default=None, pattern=SHORT_CODE, examples=["TG"])
    timezone: str | None = None
    settings: dict[str, Any] = {}

    _zones = field_validator("timezone")(classmethod(lambda cls, v: _zone(v)))


class RegionUpdate(BaseModel):
    name: str | None = None
    short_code: str | None = Field(default=None, pattern=SHORT_CODE)
    timezone: str | None = None
    settings: dict[str, Any] | None = None
    status: Status | None = None

    _zones = field_validator("timezone")(classmethod(lambda cls, v: _zone(v)))


class RegionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    name: str
    short_code: str | None = None
    timezone: str | None
    settings: dict[str, Any]
    status: Status


# ── Cities ────────────────────────────────────────────────────────────────────

class CityCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,4}$", examples=["IN-TG-HYD"])
    name: str = Field(min_length=2, max_length=100)
    center_lat: float = Field(ge=-90, le=90)
    center_lng: float = Field(ge=-180, le=180)
    timezone: str | None = None
    service_hours: ServiceHours | None = None
    settings: dict[str, Any] = {}

    _zones = field_validator("timezone")(classmethod(lambda cls, v: _zone(v)))


class CityUpdate(BaseModel):
    name: str | None = None
    center_lat: float | None = Field(default=None, ge=-90, le=90)
    center_lng: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = None
    service_hours: ServiceHours | None = None
    settings: dict[str, Any] | None = None
    status: Status | None = None

    _zones = field_validator("timezone")(classmethod(lambda cls, v: _zone(v)))


class CityOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    name: str
    timezone: str | None
    service_hours: ServiceHours | None
    center_lat: float
    center_lng: float
    settings: dict[str, Any]
    status: Status


# ── Zones ─────────────────────────────────────────────────────────────────────

class GeoJsonPolygon(BaseModel):
    """GeoJSON Polygon: [[[lng, lat], ...]] with the first point repeated last."""

    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[tuple[float, float]]]

    @model_validator(mode="after")
    def ring(self) -> "GeoJsonPolygon":
        if len(self.coordinates) != 1:
            raise ValueError("One outer ring only (no holes)")
        ring = self.coordinates[0]
        if len(ring) < 4 or ring[0] != ring[-1]:
            raise ValueError("A ring needs at least 3 corners and must end where it starts")
        for lng, lat in ring:
            if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise ValueError("Coordinates are [lng, lat] in degrees")
        return self


class ZoneCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    polygon: GeoJsonPolygon
    min_order: Decimal | None = Field(default=None, ge=0)
    color: str = Field(default="#0B5D66", pattern=r"^#[0-9A-Fa-f]{6}$")
    status: Status = "draft"


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    polygon: GeoJsonPolygon | None = None
    min_order: Decimal | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    status: Literal["draft", "beta", "live"] | None = None


class ZonePause(BaseModel):
    reason: str = Field(min_length=3, max_length=200, examples=["Heavy rain"])
    until: datetime | None = Field(default=None, description="Resumes on its own at this time")


class ZoneOut(BaseModel):
    id: uuid.UUID
    city_code: str
    name: str
    polygon: GeoJsonPolygon
    area_km2: float
    min_order: Decimal | None
    color: str
    status: Status
    pause_reason: str | None
    paused_until: datetime | None


# ── Composite views ───────────────────────────────────────────────────────────

class CitySummary(CityOut):
    zone_count: int
    live_zone_count: int
    launch_checklist: dict[str, bool]
    waitlist: int = 0  # "Notify me" sign-ups for this city (demand)


class RegionSummary(RegionOut):
    cities: list[CitySummary]


class CountrySummary(CountryOut):
    regions: list[RegionSummary]


class SettingValue(BaseModel):
    key: str
    value: Any
    source: str = Field(description="Where the value comes from: a country, state or city name")
    source_level: Literal["country", "region", "city"]


class CityDetail(CitySummary):
    country: CountryOut
    region: RegionOut
    zones: list[ZoneOut]
    effective_settings: list[SettingValue]


class LocateResult(BaseModel):
    serviceable: bool
    reason: str | None = Field(default=None, description="Why not, in plain words")
    country_code: str | None = None
    region_code: str | None = None
    region_short_code: str | None = Field(default=None, description='The state\'s short code ("ID"): the app\'s "Boise, ID"')
    city_code: str | None = None
    city_name: str | None = None
    zone_id: uuid.UUID | None = None
    zone_name: str | None = None
    min_order: Decimal | None = None
    currency: str | None = None
    status: Status | None = None
    timezone: str | None = Field(default=None, description="The city's own time zone")


class DemandCity(BaseModel):
    city_code: str
    city_name: str
    country: str
    status: str
    signups: int
    with_consent: int
    last_at: datetime | None


class DemandText(BaseModel):
    """Cities the visitor typed that aren't in Markets yet."""

    text: str
    signups: int
    last_at: datetime | None


class Demand(BaseModel):
    cities: list[DemandCity]
    suggested: list[DemandText]
