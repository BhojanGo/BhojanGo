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
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.rider import RiderProfile
from core_api.modules.identity.models.user import User
from core_api.modules.identity.schemas.user import AuthTokensResponse, Language
from core_api.modules.identity.service.auth import issue_tokens
from core_api.modules.legal import service as legal
from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from shared.db import get_db
from shared.texts import DELIVERY_SIGN_UP, language_for, pick

router = APIRouter(tags=["Sign-up"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[CurrentUser, Depends(get_current_user)]


class RiderApply(BaseModel):
    """Who is signing up to deliver, and where. The date of birth and the vehicle
    are checked against the country's rules (Markets -> Delivery partners:
    GET /delivery/sign-up?country= lists them for the form)."""

    full_name: str = Field(min_length=2, max_length=80)
    city_code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")
    date_of_birth: date
    vehicle: str = Field(pattern=r"^[a-z_]{2,20}$", examples=["motorcycle"])
    # The form's language ("hi"): a refusal's message is written in it.
    language: Language | None = None


class KitchenApply(BaseModel):
    """The kitchen's name and city start an application; the address, cuisines and
    map pin can come now (the tablet app sends them) or later, as the application's
    first step (PUT /restaurants/{id}/business)."""

    full_name: str = Field(min_length=2, max_length=80, description="Your name")
    kitchen_name: str = Field(min_length=2, max_length=120)
    city_code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")
    street: str | None = Field(default=None, min_length=3, max_length=200)
    area: str | None = Field(default=None, min_length=2, max_length=80)
    zip: str | None = Field(default=None, min_length=3, max_length=12)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    cuisines: list[str] | None = Field(default=None, min_length=1, max_length=5)


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
async def rider_apply(data: RiderApply, request: Request, me: Me, db: DB) -> AuthTokensResponse:
    """Become a rider applicant: then the onboarding checklist (licence, insurance,
    payout account, background check). Admins review in Partners → Rider documents.
    Refused with 422 when the applicant is younger than the country's minimum age
    (UNDER_AGE, with min_age), the vehicle isn't one the country allows (VEHICLE,
    with vehicles) or the date of birth can't be right (DOB); a country without
    rules uses the defaults in markets.service.delivery.sign_up_rules."""
    from core_api.modules.markets.service import delivery

    _, _, country = await _city(db, data.city_code)
    # The country's rules, on the country's own date (a birthday counts from midnight there).
    rules = delivery.sign_up_rules(country.settings)
    why = delivery.check_applicant(rules, data.date_of_birth, data.vehicle, datetime.now(ZoneInfo(country.timezone)).date())
    if why is not None:
        row = await db.get(User, me.id)
        lang = language_for(data.language or (row.preferred_locale if row else None))
        text = pick(DELIVERY_SIGN_UP[{"DOB": "dob", "UNDER_AGE": "under_age", "VEHICLE": "vehicle"}[why]], lang)
        extra = {"min_age": rules["min_age"]} if why == "UNDER_AGE" else {"vehicles": rules["vehicles"]} if why == "VEHICLE" else {}
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": why, "message": text.format(age=rules["min_age"]), **extra})
    user = await _switch(db, me, "driver")
    user.full_name, user.country = data.full_name.strip(), country.code
    profile = await db.get(RiderProfile, user.id)
    if profile is None:
        db.add(RiderProfile(user_id=user.id, date_of_birth=data.date_of_birth, vehicle=data.vehicle))
    else:
        profile.date_of_birth, profile.vehicle = data.date_of_birth, data.vehicle
    await db.flush()
    # Applying is agreeing to the Terms, Privacy and (once the country publishes them) the delivery partner terms.
    await legal.record_acceptance(db, user.id, country.code, legal.ROLE_KINDS["driver"], language=user.preferred_locale,
                                  client=legal.client_info(request))
    await db.refresh(user)  # updated_at is set by the database
    return await issue_tokens(db, user)


@router.post("/restaurants/apply", response_model=KitchenApplied, status_code=status.HTTP_201_CREATED)
async def kitchen_apply(data: KitchenApply, request: Request, me: Me, db: DB) -> KitchenApplied:
    """Apply with a kitchen from a signed-in account (a customer account with no
    orders becomes the kitchen partner's): it's created pending approval in a live,
    beta or coming-soon city, and the partner application (business details, FSSAI,
    GST and bank, menu) follows. Admins approve it in Partners -> Applications.
    A new visitor uses POST /kitchens/apply (email and password) instead."""
    from core_api.modules.catalog.service.applications import kitchen_city, open_kitchen

    city, region, country = await kitchen_city(db, data.city_code)
    user = await _switch(db, me, "restaurant_owner")
    user.full_name, user.country = data.full_name.strip(), country.code
    r = await open_kitchen(db, user.id, data.kitchen_name, city, region, country, street=data.street, area=data.area,
                           zip_code=data.zip, lat=data.lat, lng=data.lng, cuisines=data.cuisines)
    await legal.record_acceptance(db, user.id, country.code, legal.ROLE_KINDS["restaurant_owner"],
                                  language=user.preferred_locale, client=legal.client_info(request))
    await db.refresh(user)
    tokens = await issue_tokens(db, user)
    return KitchenApplied(**tokens.model_dump(), restaurant_id=str(r.id))
