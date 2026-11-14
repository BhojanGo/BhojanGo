"""Self sign-up (Phase 3, B1). A person signs in with their phone (a new
number becomes a customer account) and then applies:

- POST /riders/apply in the rider app: the account becomes a rider applicant
  and goes through the onboarding checklist; admins review the documents.
- POST /restaurants/apply on the web or the partner app: the account becomes a
  partner with a kitchen pending approval; the partner application (FSSAI,
  GST and bank, menu) follows and admins approve it.

One account has one role, so a number that already orders food can't also
ride or run a kitchen: use another number. Both return new tokens, because
the role in the old ones is no longer right.
"""
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.user import User
from core_api.modules.identity.schemas.user import AuthTokensResponse
from core_api.modules.identity.service.auth import issue_tokens
from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from shared.db import get_db

router = APIRouter(tags=["Sign-up"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[CurrentUser, Depends(get_current_user)]


class RiderApply(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    city_code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")


class KitchenApply(BaseModel):
    full_name: str = Field(min_length=2, max_length=80, description="Your name")
    kitchen_name: str = Field(min_length=2, max_length=120)
    city_code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")
    street: str = Field(min_length=3, max_length=200)
    area: str = Field(min_length=2, max_length=80)
    zip: str = Field(min_length=3, max_length=12)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    cuisines: list[str] = Field(min_length=1, max_length=5)


class KitchenApplied(AuthTokensResponse):
    restaurant_id: str


async def _city(db: AsyncSession, code: str):  # type: ignore[no-untyped-def]
    from core_api.modules.markets.models import City, Country, Region

    row = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                            .join(Country, Country.id == City.country_id).where(City.code == code))).first()
    if row is None or row[0].status not in ("live", "beta"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "CITY", "message": "We're not in that city yet"})
    return row


async def _switch(db: AsyncSession, me: CurrentUser, to: str) -> User:
    """Make the signed-in account a rider or a partner (only a fresh account)."""
    from core_api.modules.orders.models.order import Order

    user = await db.get(User, me.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found")
    if me.admin:  # admins don't sign up as riders or partners with their admin account
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "ADMIN", "message": "Use a separate number to apply"})
    if user.role == to:
        return user
    if user.role != "customer":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "ROLE", "message": "This account can't apply. Use another phone number."})
    orders = (await db.execute(select(func.count(Order.id)).where(Order.customer_id == user.id))).scalar() or 0
    if orders:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "HAS_ORDERS", "message": "This number orders food on BhojanGo. Use another number to sign up."})
    user.role = to
    return user


@router.post("/riders/apply", response_model=AuthTokensResponse)
async def rider_apply(data: RiderApply, me: Me, db: DB) -> AuthTokensResponse:
    """Become a rider applicant: then the onboarding checklist (licence, insurance,
    payout account, background check). Admins review in Partners → Rider documents."""
    _, _, country = await _city(db, data.city_code)
    user = await _switch(db, me, "driver")
    user.full_name, user.country = data.full_name.strip(), country.code
    await db.flush()
    await db.refresh(user)  # updated_at is set by the database
    return await issue_tokens(db, user)


def _slug(name: str, area: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{name} {area}".lower()).strip("-")[:60]
    return f"{base}-{uuid.uuid4().hex[:4]}"


@router.post("/restaurants/apply", response_model=KitchenApplied, status_code=status.HTTP_201_CREATED)
async def kitchen_apply(data: KitchenApply, me: Me, db: DB) -> KitchenApplied:
    """Apply with a kitchen: it's created pending approval and the partner
    application (FSSAI, GST and bank, menu) follows. Admins approve it in
    Partners → Applications."""
    from core_api.modules.catalog.models.restaurant import Restaurant

    city, region, country = await _city(db, data.city_code)
    user = await _switch(db, me, "restaurant_owner")
    user.full_name, user.country = data.full_name.strip(), country.code
    r = Restaurant(
        name=data.kitchen_name.strip(), slug=_slug(data.kitchen_name, data.area), owner_id=user.id, description="",
        cuisine_types=[c.strip() for c in data.cuisines if c.strip()], logo_url=None, cover_url=None,
        address={"street": data.street, "city": city.name, "state": region.name, "zip": data.zip, "country": country.code,
                 "lat": data.lat, "lng": data.lng, "landmark": data.area},
        lat=data.lat, lng=data.lng, rating=0, review_count=0, is_open=True, delivery_time_min=30, delivery_time_max=45,
        minimum_order_amount=0, delivery_fee=0, currency=country.currency, country=country.code, city=city.name, tags=[],
        status="pending_approval", is_active=True, avg_prep_minutes=20,
    )
    # Their terms: the city's live commission rule (default tier) -- what the application shows.
    from decimal import Decimal

    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    rules = await RuleService(db).resolve(Context(country=country.code, region=region.code, city=city.code))
    rate = rules.get("commission:rate")
    if rate:
        from core_api.modules.rules.service.templates import commission_percent

        r.commission_rate = commission_percent(rate.template, rate.params, None) / 100
    db.add(r)
    await db.flush()
    await db.refresh(user)
    tokens = await issue_tokens(db, user)
    return KitchenApplied(**tokens.model_dump(), restaurant_id=str(r.id))
