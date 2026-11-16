"""The website's "Add your kitchen" page (R8 F7). Public.

  GET  /kitchens/terms?country=IN   what a kitchen partner gets in a country, as data:
                                    commission from the live rules (range, tiers, each
                                    city's starting rate), the payout schedule, the
                                    documents to have ready (Markets setting) and the
                                    cities a kitchen can apply in (live, beta, coming soon)
  POST /kitchens/apply              a new visitor starts an application: a kitchen
                                    partner account (email + password, phone) and the
                                    kitchen, pending approval; returns tokens (signed in)

A signed-in customer applies with POST /restaurants/apply instead (identity/signup.py).
"""
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.schemas.user import MessageResponse
from shared.client_ip import client_ip
from shared.db import get_db

router = APIRouter(prefix="/kitchens", tags=["Kitchen partners (public)"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
limiter = Limiter(key_func=client_ip)
MIN_PASSWORD = 10


class Tier(BaseModel):
    tier: str
    percent: Decimal


class CommissionTerms(BaseModel):
    """Commission is a percentage of the food subtotal only (never of delivery,
    fees, tax or tips), from the country's and cities' live commission:rate rules."""

    base: Literal["food_subtotal"] = "food_subtotal"
    percent_min: Decimal
    percent_max: Decimal
    starting_percent: Decimal | None = Field(description="A new kitchen's rate at country level (the default tier)")
    tiers: list[Tier] = Field(default=[], description="The country rule's tiers, when it is percent_by_tier")
    flat_per_order: Decimal | None = Field(default=None, description="A fixed amount per order on top, if a rule sets one")


class PayoutTerms(BaseModel):
    frequency: Literal["weekly", "biweekly"] = "weekly"
    day: Literal["mon", "tue", "wed", "thu", "fri"] = "mon"
    hold_days: int = 2


class TermsCity(BaseModel):
    code: str
    name: str
    region: str
    status: Literal["live", "soon"]
    beta: bool
    starting_percent: Decimal | None


class KitchenDocument(BaseModel):
    key: str
    title: str
    why: str


class KitchenTerms(BaseModel):
    country: str
    country_name: str
    currency: str
    phone_code: str
    tax_regime: str
    commission: CommissionTerms | None = Field(description="None when the country has no commission rule live yet")
    payout: PayoutTerms
    documents: list[KitchenDocument] = Field(description="Markets setting kitchen_documents; empty: none configured")
    cities: list[TermsCity]


def _tiers(rule) -> list[Tier]:  # type: ignore[no-untyped-def]
    if rule is None or rule.template != "percent_by_tier":
        return []
    return [Tier(tier=k, percent=Decimal(str(v))) for k, v in sorted(rule.params["tiers"].items())]


def _percents(rule) -> list[Decimal]:  # type: ignore[no-untyped-def]
    if rule is None:
        return []
    if rule.template == "percent":
        return [Decimal(str(rule.params["percent"]))]
    return [Decimal(str(v)) for v in rule.params["tiers"].values()]


@router.get("/terms", response_model=KitchenTerms)
async def terms(db: DB, country: str = Query(pattern=r"^[A-Za-z]{2}$"),
                language: str = Query(default="en", pattern=r"^[a-z]{2}$")) -> KitchenTerms:
    """What a kitchen partner gets in this country, from live data (404: not a public country)."""
    from core_api.modules.markets.api.v1.public import build_directory
    from core_api.modules.markets.models import Country
    from core_api.modules.markets.service import kitchen_docs
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService
    from core_api.modules.rules.service.templates import commission_percent

    code = country.upper()
    d = await build_directory(db)
    k = next((c for c in d.countries if c.code == code), None)
    row = (await db.execute(select(Country).where(Country.code == code))).scalar_one_or_none()
    if k is None or row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "COUNTRY", "message": "We're not in that country yet"})
    service = RuleService(db)
    national = await service.resolve(Context(country=code))
    rate, flat = national.get("commission:rate"), national.get("commission:flat_per_order")
    sched = national.get("commission:payout_schedule")
    percents = _percents(rate)
    cities = []
    for region in k.regions:
        for c in region.cities:
            picked = await service.resolve(Context(country=code, region=region.code, city=c.code))
            city_rate = picked.get("commission:rate")
            percents += _percents(city_rate)
            cities.append(TermsCity(code=c.code, name=c.name, region=region.name, status=c.status, beta=c.beta,
                                    starting_percent=commission_percent(city_rate.template, city_rate.params, None) if city_rate else None))
    commission = None
    if percents:
        commission = CommissionTerms(
            percent_min=min(percents), percent_max=max(percents), tiers=_tiers(rate),
            starting_percent=commission_percent(rate.template, rate.params, None) if rate else None,
            flat_per_order=Decimal(str(flat.params["amount"])) if flat and Decimal(str(flat.params["amount"])) > 0 else None)
    payout = PayoutTerms(**{key: sched.params[key] for key in ("frequency", "day", "hold_days") if key in sched.params}) if sched else PayoutTerms()
    return KitchenTerms(country=code, country_name=k.name, currency=k.currency, phone_code=k.phone_code, tax_regime=k.tax_regime,
                        commission=commission, payout=payout,
                        documents=[KitchenDocument(**x) for x in kitchen_docs.localized(row.settings, language)], cities=cities)


class KitchenSignUp(BaseModel):
    """A new visitor starts an application on the website: their account (they sign
    in with this email and password, or with the phone and a code) and the kitchen."""

    kitchen_name: str = Field(min_length=2, max_length=120)
    city_code: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")
    full_name: str = Field(min_length=2, max_length=80, description="The contact person's name")
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$", examples=["+919876543210"])
    email: EmailStr
    password: str = Field(min_length=1, max_length=128, description=f"At least {MIN_PASSWORD} characters")
    accept_terms: bool = Field(description="Agreed to the Terms and the Privacy policy (must be true)")
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$", description="The page's language: emails use it when the country offers it")


def _refuse(code: str, message: str, http: int = status.HTTP_422_UNPROCESSABLE_CONTENT) -> HTTPException:
    return HTTPException(http, detail={"code": code, "message": message})


async def _check_password(password: str, email: str) -> None:
    """The rules for every new password (identity.service.passwords, Round 8 D5): 10+
    characters, not the email, not in a known data breach. 422 code PASSWORD, with the
    rule broken in ``reason`` (PASSWORD_TOO_SHORT, PASSWORD_BREACHED, ...)."""
    from core_api.modules.identity.service import passwords

    try:
        await passwords.validate_new_password(password, email=email)
    except passwords.PasswordRejected as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "PASSWORD", "reason": e.code, "message": e.message}) from e


def _hash(password: str) -> str:
    from core_api.modules.identity.service.passwords import hash_password  # Argon2id

    return hash_password(password)


@router.post("/apply", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute;300/hour")
async def apply(request: Request, data: KitchenSignUp, db: DB) -> MessageResponse:
    """Start an application as a new kitchen partner, the verified way every account is
    made (Round 8, D5): a 6-digit code goes to the email, and POST /auth/email/verify
    with it creates the account (role restaurant_owner) with the kitchen pending approval,
    signs them in and sends the "application started" email. The same 202 whether or not
    the email already has an account (that mailbox is told to sign in instead).
    The phone is the kitchen's contact number (kept with the kitchen); to sign in with it,
    the owner links it in Profile, verified by an SMS code.
    422 TERMS / PASSWORD (reason: PASSWORD_TOO_SHORT, PASSWORD_BREACHED, ...) / CITY /
    PHONE_COUNTRY_MISMATCH; 429 TOO_MANY_CODES."""
    from core_api.modules.catalog.service.applications import kitchen_city
    from core_api.modules.identity.service.email_auth import EmailAuthService
    from core_api.modules.markets.service import countries

    if not data.accept_terms:
        raise _refuse("TERMS", "Agree to the Terms and the Privacy policy to apply")
    email = str(data.email).lower().strip()
    await _check_password(data.password, email)
    city, region, country = await kitchen_city(db, data.city_code)
    info = await countries.require_open(db, country.code)
    countries.require_phone_in(info, data.phone)
    wanted = f"{data.language}-{country.code}" if data.language else None
    locale = wanted if wanted in info.locales else info.default_locale
    message = await EmailAuthService(db).start_sign_up(
        email, data.password, info, full_name=data.full_name.strip(), language=data.language, locale=locale,
        kitchen={"name": data.kitchen_name.strip(), "city_code": data.city_code, "phone": data.phone})
    return MessageResponse(message=message)


async def open_applied_kitchen(db: AsyncSession, user, kitchen: dict) -> None:  # type: ignore[no-untyped-def]
    """After the emailed code: the kitchen pending approval, the accepted terms and the
    "application started" email (identity.service.email_auth calls this)."""
    from core_api.modules.catalog.service.applications import kitchen_city, open_kitchen
    from shared import notify
    from shared.texts import KITCHEN_APPLIED, pick

    city, region, country = await kitchen_city(db, kitchen["city_code"])
    r = await open_kitchen(db, user.id, kitchen["name"], city, region, country)
    if kitchen.get("phone"):
        # The kitchen's contact number, not a sign-in (it isn't verified).
        r.address = {**(r.address or {}), "phone": kitchen["phone"]}
        await db.flush()
    await _record_acceptance(db, user.id, country.code)
    language = (user.preferred_locale or "en").split("-")[0]
    body = (f"<p>{pick(KITCHEN_APPLIED['body'], language).format(kitchen=_esc(r.name))}</p>"
            f"<p>{_esc(pick(KITCHEN_APPLIED['next'], language))}</p>")
    await notify.send("email", user.email, body, subject=pick(KITCHEN_APPLIED["subject"], language), country=country.code)


def _esc(text: str) -> str:
    import html

    return html.escape(text)


async def _record_acceptance(db: AsyncSession, user_id, country: str) -> None:  # type: ignore[no-untyped-def]
    """Record the Terms and Privacy versions they accepted (workstream F10's legal
    module, once it exists; until then the account's creation is the record)."""
    try:
        from core_api.modules.legal.service import record_acceptance  # type: ignore[import-not-found]
    except ImportError:
        return
    await record_acceptance(db, user_id, country, kinds=("terms", "privacy"))
