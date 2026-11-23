"""Deliver with BhojanGo (the website's /deliver page): what a delivery partner
earns in a city and what it takes to start, from the city's live rules and the
country's Markets settings. Nothing on the page is typed in: an admin changing
the rider pay rule or the requirements changes the page.

  GET /delivery/terms?city=IN-TG-HYD
  GET /delivery/sign-up?country=IN   (who can sign up: the age and vehicles the forms offer)
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.markets.api.v1.public import build_directory
from core_api.modules.markets.service import delivery
from core_api.modules.pricing.service.engine import money, rider_base_pay
from shared.db import get_db

router = APIRouter(prefix="/delivery", tags=["Delivery partners (public)"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


class TermsCity(BaseModel):
    code: str
    name: str
    region: str


class ExampleTrip(BaseModel):
    """One trip as the engine pays it (rider_pay base_distance_wait), before tips."""

    distance: Decimal = Field(description="Restaurant to customer, in the country's distance unit")
    base: Decimal
    per_unit: Decimal
    distance_pay: Decimal
    per_wait_minute: Decimal
    free_wait_minutes: int
    total: Decimal = Field(description="base + distance_pay (no waiting, no tip)")


class Payout(BaseModel):
    frequency: Literal["weekly", "biweekly"]
    day: str  # mon..fri: the day the run is made


class Document(BaseModel):
    key: str  # e.g. driving_licence, vehicle_rc_insurance (the website words it)
    step: Literal["licence", "insurance", "payout", "background_check"]  # the delivery app's onboarding step


class Requirements(BaseModel):
    min_age: int | None = None
    vehicles: list[str]  # keys: motorcycle, scooter, electric_scooter, car
    papers: list[Document]  # (not "documents": public schemas never name documents, test_public_contract)


class AppLinks(BaseModel):
    android: str | None = None  # Play Store, once published (Markets setting)
    ios: str | None = None  # App Store, once published


class DeliveryTerms(BaseModel):
    city: TermsCity
    cities: list[TermsCity] = Field(description="The country's live cities (the page's city picker)")
    country: str
    currency: str
    distance_unit: str
    phone_code: str
    example: ExampleTrip | None = None  # None: the city has no rider pay rule yet
    # R31: the city's delivery bands (road distance up to, fee): a trip pays its band's fee + the tip
    bands: list[dict[str, Decimal]] | None = None
    hourly_floor: Decimal | None = None  # per active hour (accepting to delivering), before tips
    batch_bonus: Decimal | None = None  # each extra drop-off of a batched trip
    tips_percent: int = Field(default=100, description="The share of every tip the delivery partner gets "
                                                       "(the engine's split: rider = pay + the whole tip)")
    pay_schedule: Payout | None = None  # when pay is sent (the payout_schedule rule)
    requirements: Requirements
    apps: AppLinks


@router.get("/terms", response_model=DeliveryTerms)
async def terms(db: DB, city: str = Query(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")) -> DeliveryTerms:
    """A live city's delivery partner pay (an example trip priced by the engine, the
    hourly floor, the batch bonus, tips, payout cadence) and the country's
    requirements and app links. Public; 404 for a city that isn't live."""
    from core_api.modules.markets.models import Country
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService
    from sqlalchemy import select

    d = await build_directory(db)
    for k in d.countries:
        live = [(r, c) for r in k.regions for c in r.cities if c.status == "live"]
        hit = next(((r, c) for r, c in live if c.code == city), None)
        if hit is None:
            continue
        region, c = hit
        country = (await db.execute(select(Country).where(Country.code == k.code))).scalar_one()
        resolved = await RuleService(db).resolve(Context(country=k.code, region=region.code, city=c.code))
        t = delivery.terms(country.settings)
        example = None
        pay = resolved.get("rider_pay:base_distance_wait")
        fee = resolved.get("delivery_fee")
        bands = None
        if fee is not None and fee.template == "distance_slabs":
            # R31: a trip pays the order's delivery fee (its distance band) and the whole tip; no waiting pay
            bands = [{"up_to": Decimal(str(b["up_to"])), "fee": money(b["fee"])} for b in fee.params["slabs"]]
            dist = t["example_distance"]
            band = next((b for b in bands if Decimal(str(dist)) <= b["up_to"]), bands[-1])
            example = ExampleTrip(distance=dist, base=band["fee"], per_unit=Decimal(0), distance_pay=Decimal(0),
                                  per_wait_minute=Decimal(0), free_wait_minutes=0, total=band["fee"])
        elif fee is not None and fee.template == "base_per_distance":
            # R30: a trip pays the order's delivery fee (base + per km/mi) and the whole tip; no waiting pay
            p, dist = fee.params, t["example_distance"]
            base, per = money(p["base"]), Decimal(str(p["per_unit"]))
            example = ExampleTrip(distance=dist, base=base, per_unit=per, distance_pay=money(per * Decimal(str(dist))),
                                  per_wait_minute=Decimal(0), free_wait_minutes=0, total=money(base + per * Decimal(str(dist))))
        elif pay is not None:
            p, dist = pay.params, t["example_distance"]
            total = rider_base_pay(p, dist, 0)
            base = money(p["base"])
            example = ExampleTrip(distance=dist, base=base, per_unit=Decimal(str(p["per_unit"])), distance_pay=total - base,
                                  per_wait_minute=Decimal(str(p.get("per_wait_minute", 0))),
                                  free_wait_minutes=int(p.get("free_wait_minutes", 0)), total=total)
        floor = resolved.get("rider_pay:hourly_floor")
        bonus = resolved.get("rider_pay:batch_bonus")
        sched = resolved.get("commission:payout_schedule")
        return DeliveryTerms(
            city=TermsCity(code=c.code, name=c.name, region=region.name),
            cities=[TermsCity(code=x.code, name=x.name, region=r.name) for r, x in live],
            country=k.code, currency=k.currency, distance_unit=k.distance_unit, phone_code=k.phone_code,
            example=example, bands=bands,
            hourly_floor=Decimal(str(floor.params["per_active_hour"])) if floor else None,
            batch_bonus=Decimal(str(bonus.params["per_extra_order"])) if bonus else None,
            pay_schedule=Payout(frequency=sched.params.get("frequency", "weekly"), day=sched.params.get("day", "mon")) if sched else None,
            requirements=Requirements(min_age=t["min_age"], vehicles=t["vehicles"],
                                      papers=[Document(key=d, step=delivery.APP_STEP[d]) for d in t["documents"]]),  # type: ignore[arg-type]
            apps=AppLinks(**t["app_links"]),
        )
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "We don't deliver in that city yet"})


class SignUpRules(BaseModel):
    """What the delivery partner sign-up forms ask for in a country (the web's /deliver
    and the BhojanGo Delivery app's Join): POST /riders/apply checks the same rules."""

    country: str
    min_age: int = Field(description="Applicants must be at least this old on the country's date")
    vehicles: list[str] = Field(description="The vehicles the country allows (keys: motorcycle, scooter, electric_scooter, car)")
    today: date = Field(description="The country's date now: the form's latest date of birth and its age check")
    rules_set: bool = Field(description="False: the country has no rules yet and the platform defaults apply")


@router.get("/sign-up", response_model=SignUpRules)
async def sign_up_rules(db: DB, country: str = Query(pattern=r"^[A-Z]{2}$")) -> SignUpRules:
    """The minimum age and allowed vehicles for signing up to deliver in a country
    (Markets -> Delivery partners), with the platform defaults when it has none. Public;
    404 for a country we don't operate in."""
    from zoneinfo import ZoneInfo

    from sqlalchemy import select

    from core_api.modules.markets.models import Country

    k = (await db.execute(select(Country).where(Country.code == country))).scalar_one_or_none()
    if k is None or k.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "We don't operate in that country"})
    r = delivery.sign_up_rules(k.settings)
    return SignUpRules(country=k.code, min_age=r["min_age"], vehicles=r["vehicles"], rules_set=r["rules_set"],
                       today=datetime.now(ZoneInfo(k.timezone)).date())
