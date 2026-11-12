import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Status = Literal["draft", "beta", "live", "paused"]
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


# ── Countries ─────────────────────────────────────────────────────────────────

class CountryCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2}$", examples=["IN"])
    name: str = Field(min_length=2, max_length=100)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    locales: list[str] = Field(min_length=1, examples=[["en-IN", "hi-IN", "te-IN"]])
    timezone: str
    distance_unit: Literal["km", "mi"] = "km"
    phone_code: str = Field(pattern=r"^\+\d{1,4}$")
    payment_providers: list[str] = Field(min_length=1)
    tax_regime: Literal["gst", "us_sales_tax"]
    settings: dict[str, Any] = {}


class CountryUpdate(BaseModel):
    name: str | None = None
    locales: list[str] | None = None
    timezone: str | None = None
    distance_unit: Literal["km", "mi"] | None = None
    payment_providers: list[str] | None = None
    tax_regime: Literal["gst", "us_sales_tax"] | None = None
    settings: dict[str, Any] | None = None
    status: Status | None = None


class CountryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    name: str
    currency: str
    locales: list[str]
    timezone: str
    distance_unit: str
    phone_code: str
    payment_providers: list[str]
    tax_regime: str
    settings: dict[str, Any]
    status: Status


# ── Regions (states) ──────────────────────────────────────────────────────────

class RegionCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}$", examples=["IN-TG"])
    name: str = Field(min_length=2, max_length=100)
    timezone: str | None = None
    settings: dict[str, Any] = {}


class RegionUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    settings: dict[str, Any] | None = None
    status: Status | None = None


class RegionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    code: str
    name: str
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


class CityUpdate(BaseModel):
    name: str | None = None
    center_lat: float | None = Field(default=None, ge=-90, le=90)
    center_lng: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = None
    service_hours: ServiceHours | None = None
    settings: dict[str, Any] | None = None
    status: Status | None = None


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
    city_code: str | None = None
    city_name: str | None = None
    zone_id: uuid.UUID | None = None
    zone_name: str | None = None
    min_order: Decimal | None = None
    currency: str | None = None
    status: Status | None = None
    timezone: str | None = Field(default=None, description="The city's own time zone")
