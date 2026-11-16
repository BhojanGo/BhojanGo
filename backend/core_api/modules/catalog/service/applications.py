"""A new kitchen partner's kitchen (B1, R8 F7): created pending approval, with the
city's live commission as its terms. Shared by the signed-in path
(POST /restaurants/apply) and the website's new-account path (POST /kitchens/apply).

A kitchen can apply in a city that is live, in beta or coming soon (kitchens join
before a city opens). Only the name and the city are needed to start: the street,
area, PIN/ZIP, cuisines and map pin are the application's first step
("Business details"), which can be filled in later.
"""
import re
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.restaurant import Restaurant

APPLY_STATUSES = ("live", "beta", "soon")


async def kitchen_city(db: AsyncSession, code: str):  # type: ignore[no-untyped-def]
    """(city, region, country) for a city a kitchen can apply in, else 422 CITY."""
    from core_api.modules.markets.models import City, Country, Region

    row = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                            .join(Country, Country.id == City.country_id).where(City.code == code))).first()
    if row is None or row[0].status not in APPLY_STATUSES or row[2].status == "draft":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "CITY", "message": "We're not in that city yet"})
    return row


def slug(name: str, area: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{name} {area}".lower()).strip("-")[:60]
    return f"{base}-{uuid.uuid4().hex[:4]}"


async def starting_commission(db: AsyncSession, country: str, region: str, city: str, tier: str | None = None) -> Decimal | None:
    """The city's live commission rule for a new kitchen (its default tier), in percent."""
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService
    from core_api.modules.rules.service.templates import commission_percent

    rate = (await RuleService(db).resolve(Context(country=country, region=region, city=city))).get("commission:rate")
    return commission_percent(rate.template, rate.params, tier) if rate else None


async def open_kitchen(db: AsyncSession, owner_id: uuid.UUID, kitchen_name: str, city, region, country, *,  # type: ignore[no-untyped-def]
                       street: str | None = None, area: str | None = None, zip_code: str | None = None,
                       lat: float | None = None, lng: float | None = None, cuisines: list[str] | None = None) -> Restaurant:
    """The kitchen, pending approval. Without a map pin it sits at the city centre
    until the business details step sets it."""
    lat = city.center_lat if lat is None else lat
    lng = city.center_lng if lng is None else lng
    address = {"city": city.name, "state": region.name, "country": country.code, "lat": lat, "lng": lng}
    if street:
        address |= {"street": street.strip(), "zip": (zip_code or "").strip(), "landmark": (area or "").strip()}
    r = Restaurant(
        name=kitchen_name.strip(), slug=slug(kitchen_name, area or city.name), owner_id=owner_id, description="",
        cuisine_types=[c.strip() for c in (cuisines or []) if c.strip()], logo_url=None, cover_url=None,
        address=address, lat=lat, lng=lng, rating=0, review_count=0, is_open=True, delivery_time_min=30, delivery_time_max=45,
        minimum_order_amount=0, delivery_fee=0, currency=country.currency, country=country.code, city=city.name, tags=[],
        status="pending_approval", is_active=True, avg_prep_minutes=20,
    )
    percent = await starting_commission(db, country.code, region.code, city.code)
    if percent is not None:
        r.commission_rate = percent / 100
    db.add(r)
    await db.flush()
    return r


def business_done(r: Restaurant) -> bool:
    """The first step: name, street address and a pin."""
    return bool(r.name and r.lat is not None and (r.address or {}).get("street"))
