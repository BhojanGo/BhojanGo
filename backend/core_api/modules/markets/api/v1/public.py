"""Public markets data for the website (web v2). Nothing about a city, state or
country is typed into the website: it reads it all from here, so launching a
city is an admin action in Markets (docs/design/web/WebDataRules.html).

  /markets/directory              countries -> states -> cities (live and coming soon), counts
  /markets/cities/{country}/{slug} one public city (its page)
  /markets/areas?q=               find an area by name (the address box; no paid geocoder)
  /markets/hint                   "Looks like you're near ..." from the visitor's IP (a hint only)
  /markets/waitlist               "Notify me" for coming-soon cities and unserved addresses
"""
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.markets.models import City, Country, LaunchWaitlist, Region, Zone
from core_api.modules.markets.service import rules
from core_api.modules.pricing.schemas import CityPricing
from shared.db import get_db

router = APIRouter(prefix="/markets", tags=["Markets (public)"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


def slugify(name: str) -> str:
    """URL part for a city or country name ("Visakhapatnam" -> "visakhapatnam")."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def public_status(country: Country, region: Region, city: City) -> str | None:
    """What a visitor sees for a city: "live" (orders open), "soon" (announced), or
    None (hidden: still a draft, or closed). A soon city needs its country to be past
    draft; its state may still be a draft (the state opens with its first city)."""
    if rules.chain_open(country.status, region.status, city.status):
        return "live"
    if city.status == "soon" and country.status != "draft":
        return "soon"
    return None


class DirCity(BaseModel):
    code: str
    name: str
    slug: str
    path: str  # /{country}/{city} on the website
    status: Literal["live", "soon"]
    beta: bool
    restaurants: int
    waiting: int = 0  # "Notify me" sign-ups for a coming-soon city (0 when live)
    lat: float
    lng: float


class DirRegion(BaseModel):
    code: str
    name: str
    cities: list[DirCity]


class DirCountry(BaseModel):
    code: str
    slug: str  # lower-case code, the first part of city URLs
    name: str
    currency: str
    locales: list[str]
    timezone: str
    distance_unit: str
    phone_code: str
    tax_regime: str  # gst | us_sales_tax: a tax invoice or a receipt
    payment_providers: list[str]
    payment_methods: list[str]  # what checkout offers (Markets settings), e.g. upi, card, wallet
    live: int
    soon: int
    regions: list[DirRegion]


class Directory(BaseModel):
    countries: list[DirCountry]
    totals: dict[str, int]  # countries, live, soon, restaurants


async def _restaurant_counts(db: AsyncSession) -> dict[tuple[str, str], int]:
    from core_api.modules.catalog.models.restaurant import Restaurant

    rows = (await db.execute(
        select(Restaurant.country, Restaurant.city, func.count(Restaurant.id))
        .where(Restaurant.status == "active", Restaurant.is_active.is_(True), Restaurant.deleted_at.is_(None))
        .group_by(Restaurant.country, Restaurant.city))).all()
    return {(c or "", (city or "").lower()): n for c, city, n in rows}


async def _waiting_counts(db: AsyncSession) -> dict[str, int]:
    """City code -> how many asked to be notified when it opens."""
    rows = (await db.execute(
        select(LaunchWaitlist.city_code, func.count(LaunchWaitlist.id))
        .where(LaunchWaitlist.city_code.is_not(None)).group_by(LaunchWaitlist.city_code))).all()
    return {code: n for code, n in rows}


async def build_directory(db: AsyncSession) -> Directory:
    rows = (await db.execute(
        select(City, Region, Country).join(Region, Region.id == City.region_id).join(Country, Country.id == City.country_id)
        .order_by(Country.name, Region.name, City.name))).all()
    counts = await _restaurant_counts(db)
    waiting = await _waiting_counts(db)
    countries: dict[str, DirCountry] = {}
    regions: dict[str, DirRegion] = {}
    for city, region, country in rows:
        st = public_status(country, region, city)
        if st is None:
            continue
        k = countries.get(country.code)
        if k is None:
            k = countries[country.code] = DirCountry(
                code=country.code, slug=country.code.lower(), name=country.name, currency=country.currency,
                locales=list(country.locales), timezone=country.timezone, distance_unit=country.distance_unit,
                phone_code=country.phone_code, tax_regime=country.tax_regime,
                payment_providers=list(country.payment_providers),
                payment_methods=list((country.settings or {}).get("payment_methods") or ["card"]),
                live=0, soon=0, regions=[])
        r = regions.get(region.code)
        if r is None:
            r = regions[region.code] = DirRegion(code=region.code, name=region.name, cities=[])
            k.regions.append(r)
        slug = slugify(city.name)
        r.cities.append(DirCity(
            code=city.code, name=city.name, slug=slug, path=f"/{k.slug}/{slug}", status=st,
            beta=st == "live" and "beta" in (country.status, region.status, city.status),
            restaurants=counts.get((country.code, city.name.lower()), 0) if st == "live" else 0,
            waiting=waiting.get(city.code, 0) if st == "soon" else 0,
            lat=city.center_lat, lng=city.center_lng))
        if st == "live":
            k.live += 1
        else:
            k.soon += 1
    out = list(countries.values())
    for k in out:  # live cities first within a state, states with live cities first
        for r in k.regions:
            r.cities.sort(key=lambda c: (c.status != "live", c.name))
        k.regions.sort(key=lambda r: (all(c.status != "live" for c in r.cities), r.name))
    return Directory(countries=out, totals={
        "countries": len(out), "live": sum(k.live for k in out), "soon": sum(k.soon for k in out),
        "restaurants": sum(c.restaurants for k in out for r in k.regions for c in r.cities)})


@router.get("/directory", response_model=Directory)
async def directory(db: DB) -> Directory:
    """Every public city, by country and state: the website's /cities page, the
    landing page's "Where we deliver", the header's country list and the sitemap."""
    return await build_directory(db)


class PublicZone(BaseModel):
    name: str
    min_order: float | None


class CityPage(BaseModel):
    code: str
    name: str
    slug: str
    status: Literal["live", "soon"]
    beta: bool
    region: dict[str, str]
    country: DirCountry
    timezone: str
    restaurants: int
    waiting: int = 0  # "Notify me" sign-ups (coming-soon cities; 0 when live)
    lat: float
    lng: float
    zones: list[PublicZone]
    pricing: CityPricing | None = None  # the city's prices from its live rules (FAQ, "from ₹25 delivery")


@router.get("/cities/{country}/{slug}", response_model=CityPage)
async def city_page(country: str, slug: str, db: DB) -> CityPage:
    """One public city by its website path (/in/hyderabad). 404 when hidden.
    ``pricing``: the city's fees from its live rules; ``waiting``: Notify-me sign-ups."""
    from core_api.modules.pricing.service.summary import city_pricing

    d = await build_directory(db)
    k = next((c for c in d.countries if c.slug == country.lower()), None)
    for r in (k.regions if k else []):
        for c in r.cities:
            if c.slug == slug.lower():
                row = (await db.execute(select(City).where(City.code == c.code))).scalar_one()
                zones = (await db.execute(select(Zone).where(Zone.city_id == row.id).order_by(Zone.name))).scalars().all()
                now = datetime.now(UTC)
                open_zones = [z for z in zones if rules.ZoneState(z.status, z.paused_until).is_open(now)]
                tz = row.timezone or k.timezone  # type: ignore[union-attr]
                pricing = await city_pricing(
                    db, country=k.code, region=r.code, city=c.code, currency=k.currency,  # type: ignore[union-attr]
                    distance_unit=k.distance_unit,  # type: ignore[union-attr]
                    zone_minimums=[(z.name, z.min_order) for z in open_zones])
                return CityPage(code=c.code, name=c.name, slug=c.slug, status=c.status, beta=c.beta,
                                region={"code": r.code, "name": r.name}, country=k, timezone=tz,  # type: ignore[arg-type]
                                restaurants=c.restaurants, waiting=c.waiting, lat=c.lat, lng=c.lng, pricing=pricing,
                                zones=[PublicZone(name=z.name, min_order=float(z.min_order) if z.min_order is not None else None)
                                       for z in open_zones])
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "No such city"})


class Area(BaseModel):
    label: str  # "Madhapur, Hyderabad"
    area: str
    city_code: str
    city_name: str
    city_path: str
    country: str
    lat: float
    lng: float
    served: bool


@router.get("/areas", response_model=list[Area])
async def areas(db: DB, q: str = Query(min_length=2, max_length=60), country: str | None = Query(default=None, max_length=2),
                limit: int = Query(default=8, ge=1, le=20)) -> list[Area]:
    """Find a delivery area or city by name, for the address box. A point inside the
    area stands in for the address until the visitor drops a pin or saves one (no
    paid geocoder: zero spend)."""
    like = f"%{q.strip()}%"
    point = func.ST_PointOnSurface(Zone.polygon)
    stmt = (select(Zone, City, Region, Country, func.ST_Y(point), func.ST_X(point))
            .join(City, City.id == Zone.city_id).join(Region, Region.id == City.region_id)
            .join(Country, Country.id == City.country_id)
            .where(or_(Zone.name.ilike(like), City.name.ilike(like))).order_by(City.name, Zone.name).limit(200))
    if country:
        stmt = stmt.where(Country.code == country.upper())
    now = datetime.now(UTC)
    out: list[Area] = []
    for zone, city, region, k, lat, lng in (await db.execute(stmt)).all():
        st = public_status(k, region, city)
        zone_open = rules.ZoneState(zone.status, zone.paused_until).is_open(now)
        if st != "live" or not zone_open:
            continue
        out.append(Area(label=f"{zone.name}, {city.name}", area=zone.name, city_code=city.code, city_name=city.name,
                        city_path=f"/{k.code.lower()}/{slugify(city.name)}", country=k.code, lat=lat, lng=lng, served=True))
    # Coming-soon cities match by name too, so the visitor can ask to be notified.
    soon = (await db.execute(
        select(City, Region, Country).join(Region, Region.id == City.region_id).join(Country, Country.id == City.country_id)
        .where(City.name.ilike(like), City.status == "soon"))).all()
    for city, region, k in soon:
        if public_status(k, region, city) == "soon" and (not country or k.code == country.upper()):
            out.append(Area(label=f"{city.name}, {region.name}", area=city.name, city_code=city.code, city_name=city.name,
                            city_path=f"/{k.code.lower()}/{slugify(city.name)}", country=k.code,
                            lat=city.center_lat, lng=city.center_lng, served=False))
    return out[:limit]


class Hint(BaseModel):
    country: str | None = None  # a public country the IP points at
    place: str | None = None  # the IP's own town, e.g. "Meridian"
    region: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    city_path: str | None = None
    served: bool = False


@router.get("/hint", response_model=Hint)
async def hint(request: Request, db: DB) -> Hint:
    """Where the visitor seems to be, from their IP: a hint only ("Looks like you're
    near ..."), never a decision. The place is named only when it's inside an open
    zone; otherwise just the country (for the header's country and language)."""
    from core_api.modules.markets.service.markets import MarketService
    from shared import geoip
    from shared.client_ip import client_ip

    found = geoip.lookup(client_ip(request))
    if not found:
        return Hint()
    d = await build_directory(db)
    country = found.country if any(k.code == found.country for k in d.countries) else None
    out = Hint(country=country)
    if country and found.lat is not None and found.lng is not None:
        loc = await MarketService(db).locate(found.lat, found.lng)
        if loc.serviceable and loc.city_code:
            k = next(k for k in d.countries if k.code == country)
            city = next((c for r in k.regions for c in r.cities if c.code == loc.city_code), None)
            if city:
                out.place, out.region = found.city or city.name, found.region
                out.city_code, out.city_name, out.city_path, out.served = city.code, city.name, city.path, True
    return out


class WaitlistIn(BaseModel):
    """Either the website's form (email + city or the visitor's own words) or the
    apps' older form (phone + where they are)."""

    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$", examples=["+12085550199"])
    city_code: str | None = Field(default=None, max_length=20)
    city_text: str | None = Field(default=None, max_length=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    consent: bool = Field(default=False, description="Agreed to one email (or SMS) when we launch there")
    locale: str | None = Field(default=None, max_length=10)
    source: Literal["soon_city", "outside_zone", "suggest_city", "app"] = "app"

    @model_validator(mode="after")
    def contact_and_place(self) -> "WaitlistIn":
        if not (self.email or self.phone):
            raise ValueError("an email or a phone number is needed")
        if not (self.city_code or (self.city_text and self.city_text.strip()) or (self.lat is not None and self.lng is not None)):
            raise ValueError("say which city (or where you are)")
        if self.email and not self.consent:
            raise ValueError("consent is needed to email you")
        return self


@router.post("/waitlist", status_code=status.HTTP_202_ACCEPTED)
async def join_waitlist(data: WaitlistIn, db: DB) -> dict:
    """"Notify me": the demand data Markets shows per city. Signing up twice for the
    same place updates the first sign-up."""
    city_code = data.city_code
    country = None
    if city_code:
        row = (await db.execute(select(City, Country).join(Country, Country.id == City.country_id)
                                .where(City.code == city_code))).first()
        if row is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail={"code": "UNKNOWN_CITY", "message": "No such city"})
        country = row[1].code
    elif data.lat is not None and data.lng is not None:
        # an unserved address: count it for the city it's in (or nearest to), if any
        from core_api.modules.markets.service.markets import MarketService

        loc = await MarketService(db).locate(data.lat, data.lng)
        city_code = loc.city_code
    text = (data.city_text or "").strip() or None
    email = data.email.lower() if data.email else None
    stmt = select(LaunchWaitlist)
    if email:
        stmt = stmt.where(LaunchWaitlist.email == email)
    else:
        stmt = stmt.where(LaunchWaitlist.phone == data.phone)
    stmt = stmt.where(LaunchWaitlist.city_code == city_code if city_code else LaunchWaitlist.city_code.is_(None))
    if not city_code:
        stmt = stmt.where(func.lower(func.coalesce(LaunchWaitlist.city_text, "")) == (text or "").lower())
    existing = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    values = dict(email=email, phone=data.phone, city_code=city_code, city_text=text, country=country, lat=data.lat,
                  lng=data.lng, locale=data.locale, source=data.source,
                  consent_at=datetime.now(UTC) if data.consent else None)
    if existing:
        for k, v in values.items():
            if v is not None:
                setattr(existing, k, v)
    else:
        db.add(LaunchWaitlist(id=uuid.uuid4(), **values))
    await db.flush()
    return {"ok": True}
