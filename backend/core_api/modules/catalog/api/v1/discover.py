"""What's near an address, for the website's home and city pages (web v2):
the kitchens that deliver there, each with its delivery fee from the rule
engine for that address, its offer and who pays for it; the cuisines; the offers.
Public (no sign-in): prices are the same for everyone at an address.

  GET /discover?lat=&lng=   an address (or a point inside an area from /markets/areas)
  GET /discover?city=CODE   a whole city (its page, for search engines): no
                            per-address fees, the city's kitchens and offers
"""
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.service.photos import cuisine_photo, photos_for
from core_api.modules.catalog.service.ratings import RatingDisplay, rating_display
from shared.db import get_db

router = APIRouter(prefix="/discover", tags=["Discover"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]

KM_PER_MI = Decimal("1.609344")
NEW_FOR_DAYS = 30
CACHE_SECONDS = 60
MIN_KITCHENS_PER_CUISINE = 2


class Offer(BaseModel):
    id: str
    title: str  # the rule's name, e.g. "10% off, up to ₹50"
    template: str  # percent_off | flat_off | free_delivery | first_order | referral
    funded_by: Literal["platform", "restaurant"]
    percent: str | None = None
    amount: str | None = None
    max_discount: str | None = None
    min_subtotal: str | None = None
    code: str | None = None  # None: applies by itself
    restaurant: dict | None = None  # {id, slug, name, path, cover_url, photo_url} for a kitchen's own offer


class Card(BaseModel):
    id: str
    slug: str
    name: str
    path: str
    cuisine_types: list[str]
    tags: list[str]
    area: str | None
    cover_url: str | None  # the kitchen's own photo
    # What to show (catalog.service.photos): the cover, else its first dish photo, else its cuisine's library photo.
    photo_url: str | None = None
    logo_url: str | None
    rating: float
    review_count: int
    rating_display: RatingDisplay  # {"new": true} below 5 ratings, else {"new": false, "stars": 4.6, "count": 23}
    is_new: bool
    open_now: bool
    opens_at: str | None  # next opening, local ISO, when closed
    eta_min: int
    eta_max: int
    distance: float | None  # in the country's unit, from the address
    delivery_fee: str | None  # from the rule engine for this address (None on a city page)
    free_delivery: bool
    offer: Offer | None


class Discover(BaseModel):
    served: bool
    reason: str | None = None
    country: str | None = None
    currency: str | None = None
    distance_unit: str | None = None
    timezone: str | None = None
    city: dict | None = None  # {code, name, path, status}
    zone: str | None = None
    restaurants: list[Card] = []
    cuisines: list[dict] = []  # [{name, count, photo?}]: cuisines with 2+ kitchens; photo omitted when none is left
    offers: list[Offer] = []


def _offer(c, restaurant: dict | None) -> Offer:  # type: ignore[no-untyped-def]
    p = c.params
    s = lambda k: str(p[k]) if p.get(k) is not None else None  # noqa: E731
    return Offer(id=str(c.rule_key), title=c.name or c.template.replace("_", " "), template=c.template,
                 funded_by=p.get("funded_by", "platform"), percent=s("percent"), amount=s("amount"),
                 max_discount=s("max_discount"), min_subtotal=s("min_subtotal") if p.get("min_subtotal") else None,
                 code=p.get("code"), restaurant=restaurant)


@router.get("", response_model=Discover)
async def discover(db: DB, lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
                   city: str | None = Query(None, pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")) -> Discover:
    if city is None and (lat is None or lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Give lat and lng, or a city code")
    from shared.redis import get_redis

    key = f"discover:{city or f'{lat:.4f},{lng:.4f}'}"
    r = await get_redis()
    cached = await r.get(key)
    if cached:
        return Discover(**json.loads(cached))
    out = await _discover(db, lat, lng, city)
    await r.set(key, out.model_dump_json(), ex=CACHE_SECONDS)
    return out


async def _discover(db: AsyncSession, lat: float | None, lng: float | None, city_code: str | None) -> Discover:
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service import geo
    from core_api.modules.catalog.service import menu as menu_svc
    from core_api.modules.markets.api.v1.public import public_status, slugify
    from core_api.modules.markets.models import City, Country, Region
    from core_api.modules.markets.service.markets import MarketService
    from core_api.modules.pricing.service.engine import CartLine, NotDeliverable, QuoteInputs, compute
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    zone_id = zone_name = None
    if city_code is None:
        loc = await MarketService(db).locate(lat, lng)  # type: ignore[arg-type]
        if not loc.serviceable:
            return Discover(served=False, reason=loc.reason,
                            city={"code": loc.city_code, "name": loc.city_name} if loc.city_code else None)
        city_code, zone_id, zone_name = loc.city_code, loc.zone_id, loc.zone_name
    row = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                            .join(Country, Country.id == City.country_id).where(City.code == city_code))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    city, region, country = row
    st = public_status(country, region, city)
    if st is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    city_path = f"/{country.code.lower()}/{slugify(city.name)}"
    base = Discover(served=st == "live" and (zone_id is not None or lat is None), country=country.code,
                    currency=country.currency, distance_unit=country.distance_unit,
                    timezone=city.timezone or region.timezone or country.timezone,
                    city={"code": city.code, "name": city.name, "path": city_path, "status": st}, zone=zone_name)
    if st != "live":
        return base

    kitchens = (await db.execute(select(Restaurant).where(
        Restaurant.country == country.code, Restaurant.city.ilike(city.name), Restaurant.status == "active",
        Restaurant.is_active.is_(True), Restaurant.deleted_at.is_(None)))).scalars().all()
    rules_svc = RuleService(db)
    now = datetime.now(UTC)
    tz = base.timezone or "UTC"
    from zoneinfo import ZoneInfo

    local = now.astimezone(ZoneInfo(tz))
    shown = await photos_for(db, kitchens)
    cards: list[Card] = []
    offers: dict[str, Offer] = {}
    for k in kitchens:
        distance_km = None
        if lat is not None and lng is not None:
            if k.lat is None or k.lng is None:
                continue
            distance_km = geo.haversine_km(k.lat, k.lng, lat, lng)
            if distance_km > float(k.delivery_radius_km):
                continue  # doesn't deliver to this address
        try:
            a = await menu_svc.availability(db, k.id)
        except menu_svc.MenuError:
            continue
        if not a.listed:
            continue
        ref = {"id": str(k.id), "slug": k.slug, "name": k.name, "path": f"{city_path}/{k.slug}", "cover_url": k.cover_url,
               "photo_url": shown.get(str(k.id))}
        resolved = await rules_svc.resolve(Context(country=country.code, region=region.code, city=city.code,
                                                   zone_id=str(zone_id) if zone_id else None, restaurant_id=str(k.id)), now)
        promos = [c for slot, c in resolved.items() if slot.startswith("promotion:") and not c.params.get("code")
                  and c.template != "referral"]
        card_offer = None
        for c in sorted(promos, key=lambda c: (c.scope_level != "restaurant", c.template != "free_delivery")):
            o = _offer(c, ref if c.scope_level == "restaurant" else None)
            offers.setdefault(o.id, o)
            card_offer = card_offer or o
        fee = None
        distance = None
        if distance_km is not None:
            distance = Decimal(str(distance_km)) / (KM_PER_MI if country.distance_unit == "mi" else 1)
            food = max(Decimal(k.minimum_order_amount or 0), Decimal("1"))
            try:
                q = compute(QuoteInputs(currency=country.currency, lines=[CartLine("Cart", 1, food)],
                                        distance=distance.quantize(Decimal("0.01")), local_time=local), resolved)
                fee = str(sum((ln.amount for ln in q.lines if ln.code == "delivery_fee"), Decimal("0")))
            except NotDeliverable:
                continue
        created = getattr(k, "created_at", None)
        cards.append(Card(
            id=str(k.id), slug=k.slug, name=k.name, path=ref["path"], cuisine_types=list(k.cuisine_types or []),
            tags=list(k.tags or []), area=(k.address or {}).get("landmark") if isinstance(k.address, dict) else None, cover_url=k.cover_url,
            photo_url=shown.get(str(k.id)), logo_url=k.logo_url,
            rating=float(k.rating or 0), review_count=int(getattr(k, "review_count", 0) or 0),
            rating_display=rating_display(k.rating, getattr(k, "review_count", 0)),
            is_new=bool(created and created > now - timedelta(days=NEW_FOR_DAYS)), open_now=a.open_now,
            opens_at=a.next_open_at.isoformat() if a.next_open_at and not a.open_now else None,
            eta_min=k.delivery_time_min, eta_max=k.delivery_time_max,
            distance=float(round(distance, 1)) if distance is not None else None, delivery_fee=fee,
            free_delivery=any(c.template == "free_delivery" for c in promos), offer=card_offer))
    cards.sort(key=lambda c: (not c.open_now, c.distance if c.distance is not None else 0, c.name))
    cuisines: dict[str, int] = {}
    for c in cards:
        for name in c.cuisine_types:
            cuisines[name] = cuisines.get(name, 0) + 1
    names = [n for n, v in sorted(cuisines.items(), key=lambda kv: (-kv[1], kv[0])) if v >= MIN_KITCHENS_PER_CUISINE]
    photos = pick_cuisine_photos(names, await _photo_candidates(db, names, kitchens, {c.id for c in cards}))
    base.restaurants = cards
    base.cuisines = [{"name": n, "count": cuisines[n], **({"photo": photos[n]} if n in photos else {})} for n in names]
    base.offers = sorted(offers.values(), key=lambda o: (o.restaurant is not None, o.title))
    return base



async def _photo_candidates(db: AsyncSession, names: list[str], kitchens: list, on_cards: set[str]) -> dict[str, list[str]]:  # type: ignore[type-arg]
    """Each cuisine's photos, best first: covers of the city's kitchens of that
    cuisine that aren't on a card in this response, then the food library's photo
    of that cuisine (R8: catalog.service.photos, e.g. Japanese -> sushi, so every
    mapped cuisine has a fitting photo even when its kitchens have none), then
    dish photos from the cuisine's kitchens, then covers that are already on a
    card (repeats a card)."""
    from core_api.modules.catalog.models.menu import MenuItem

    if not names:
        return {}
    by_kitchen: dict[str, list[str]] = {}
    ids = [k.id for k in kitchens]
    if ids:
        rows = (await db.execute(
            select(MenuItem.restaurant_id, MenuItem.image_url)
            .where(MenuItem.restaurant_id.in_(ids), MenuItem.image_url.is_not(None), MenuItem.image_url != "",
                   MenuItem.deleted_at.is_(None), MenuItem.is_available.is_(True))
            .order_by(MenuItem.restaurant_id, MenuItem.sort_order, MenuItem.name))).all()
        for rid, url in rows:
            by_kitchen.setdefault(str(rid), []).append(url)
    card_covers = {k.cover_url for k in kitchens if str(k.id) in on_cards and k.cover_url}
    card_keys = {photo_key(u) for u in card_covers}
    out: dict[str, list[str]] = {}
    for name in names:
        mine = sorted((k for k in kitchens if name.lower() in {c.lower() for c in (k.cuisine_types or [])}),
                      key=lambda k: (-(k.review_count or 0), k.name))
        covers = [k.cover_url for k in mine if k.cover_url]
        dishes = [u for k in mine for u in by_kitchen.get(str(k.id), [])]
        library = [u for u in [cuisine_photo([name])] if u and photo_key(u) not in card_keys]
        out[name] = ([u for u in covers if u not in card_covers] + library + [u for u in dishes if u not in card_covers]
                     + [u for u in covers if u in card_covers])
    return out


def photo_key(url: str) -> str:
    """The same library photo at any width is one photo ("/food/tacos-800.webp" = "/food/tacos-1600.webp")."""
    return re.sub(r"-(400|800|1600)\.webp$", "", url)


def pick_cuisine_photos(names: list[str], candidates: dict[str, list[str]]) -> dict[str, str]:
    """One photo per cuisine, never the same photo for two cuisines. Each takes
    its best photo nobody has taken yet; cuisines with fewer photos to choose
    from pick first, so a cuisine with one fitting photo isn't left without it.
    A cuisine with nothing left gets no photo."""
    used: set[str] = set()
    out: dict[str, str] = {}
    order = sorted(names, key=lambda n: (len(dict.fromkeys(candidates.get(n, []))), names.index(n)))
    for name in order:
        photo = next((u for u in candidates.get(name, []) if photo_key(u) not in used), None)
        if photo:
            used.add(photo_key(photo))
            out[name] = photo
    return out
