"""What's near an address, for the website's home and city pages (web v2):
the kitchens that deliver there, each with its delivery fee from the rule
engine for that address, its offer and who pays for it; the cuisines; the offers.
Public (no sign-in): prices are the same for everyone at an address.

  GET /discover?lat=&lng=   an address (or a point inside an area from /markets/areas)
  GET /discover?city=CODE   a whole city (its page, for search engines): no
                            per-address fees, the city's kitchens and offers
"""
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.service.photos import cuisine_photo, photos_for
from core_api.modules.catalog.service.ratings import RatingDisplay, rating_display
from shared.auth import optional_viewer
from shared.db import get_db

router = APIRouter(prefix="/discover", tags=["Discover"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Looker = Annotated[uuid.UUID | None, Depends(optional_viewer)]

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
    closed_for_now: bool = False  # R17: an admin paused it (opens_at = its "back at", if set)
    # R27: open by its hours, but its tablet isn't connected: "Not taking orders right now".
    not_taking_orders: bool = False
    eta_min: int
    eta_max: int
    distance: float | None  # in the country's unit, by road from the restaurant to the address (R31: 2 decimals)
    delivery_fee: str | None  # from the rule engine for this address (None on a city page, or when not deliverable)
    # R31: false when the address is beyond the max delivery distance / last band (the card says so; no delivery)
    deliverable: bool = True
    free_delivery: bool
    offer: Offer | None
    # R36: the restaurant takes pickup orders; "pickup only" when it can't deliver to this address but takes pickup
    pickup_enabled: bool = False
    pickup_only: bool = False
    pickup_fee_percent: str | None = None  # the pickup platform fee, e.g. "5" ("Pickup · 5% fee")
    minimum_order: str | None = None  # the restaurant's own minimum food subtotal (None: none)


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
    # R36: show the "Free delivery" filter only when a restaurant here funds a free-delivery offer itself
    free_delivery_chip: bool = False


class DishHit(BaseModel):
    """R36: a dish whose name matches the search, with its restaurant (as the menu shows it)."""
    id: str
    name: str
    price: str
    photo_url: str | None
    has_options: bool  # adding opens the dish (size, spice, add-ons) instead of adding straight away
    restaurant_id: str
    restaurant_slug: str
    restaurant_name: str
    restaurant_path: str
    open_now: bool
    deliverable: bool
    pickup_only: bool


class SearchOut(BaseModel):
    q: str
    restaurants: list[Card] = []  # name, cuisine or tag matches, in the list's order
    dishes: list[DishHit] = []  # dish name matches, in the list's order of their restaurants, then the menu's


SEARCH_DISHES_MAX = 60


@router.get("/search", response_model=SearchOut)
async def search(db: DB, viewer: Looker, q: str = Query(..., min_length=2, max_length=60),
                 lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
                 city: str | None = Query(None, pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")) -> SearchOut:
    """R36: restaurants by name, cuisine or tag, and dishes by name ("curry": every restaurant's curries),
    for a point (or a whole city), among the kitchens /discover lists there."""
    if city is None and (lat is None or lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Give lat and lng, or a city code")
    from core_api.modules.catalog.models.menu import MenuItem
    from core_api.modules.catalog.models.options import MenuItemOptionGroup
    from core_api.modules.markets.service import review

    hidden = await review.hidden_for(db, viewer)
    if hidden.city(city):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    d = await _discover(db, lat, lng, city, hide=hidden.codes, fresh=hidden.sees_review)
    needle = " ".join(q.lower().split())
    out = SearchOut(q=q)
    if not d.served or not d.restaurants:
        return out
    out.restaurants = [c for c in d.restaurants if needle in c.name.lower()
                       or any(needle in x.lower() for x in [*c.cuisine_types, *c.tags])]
    cards = {c.id: c for c in d.restaurants}
    rank = {c.id: i for i, c in enumerate(d.restaurants)}
    like = "%" + needle.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
    rows = (await db.execute(select(MenuItem).where(
        MenuItem.restaurant_id.in_([uuid.UUID(i) for i in cards]), MenuItem.name.ilike(like),
        MenuItem.deleted_at.is_(None), MenuItem.is_available.is_(True)))).scalars().all()
    with_options = set((await db.execute(select(MenuItemOptionGroup.menu_item_id).where(
        MenuItemOptionGroup.menu_item_id.in_([m.id for m in rows])))).scalars().all()) if rows else set()
    rows = sorted(rows, key=lambda m: (rank[str(m.restaurant_id)], m.sort_order, m.name))[:SEARCH_DISHES_MAX]
    for m in rows:
        c = cards[str(m.restaurant_id)]
        out.dishes.append(DishHit(
            id=str(m.id), name=m.name, price=str(m.price), photo_url=m.image_url, has_options=m.id in with_options,
            restaurant_id=c.id, restaurant_slug=c.slug, restaurant_name=c.name, restaurant_path=c.path,
            open_now=c.open_now, deliverable=c.deliverable, pickup_only=c.pickup_only))
    return out


def list_order(c: "Card") -> tuple:
    """R36: open and deliverable first, then pickup only (too far to deliver, takes pickup), then closed;
    a kitchen that's too far and takes no pickup last. Nearest first within each."""
    if c.open_now and c.deliverable:
        group = 0
    elif c.open_now and c.pickup_only:
        group = 1
    elif c.deliverable or c.pickup_only:
        group = 2
    else:
        group = 3
    return (group, c.distance if c.distance is not None else 0, c.name)


def _offer(c, restaurant: dict | None) -> Offer:  # type: ignore[no-untyped-def]
    p = c.params
    s = lambda k: str(p[k]) if p.get(k) is not None else None  # noqa: E731
    return Offer(id=str(c.rule_key), title=c.name or c.template.replace("_", " "), template=c.template,
                 funded_by=p.get("funded_by", "platform"), percent=s("percent"), amount=s("amount"),
                 max_discount=s("max_discount"), min_subtotal=s("min_subtotal") if p.get("min_subtotal") else None,
                 code=p.get("code"), restaurant=restaurant)


@router.get("", response_model=Discover)
async def discover(db: DB, viewer: Looker, lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
                   city: str | None = Query(None, pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")) -> Discover:
    """Kitchens, cuisines and offers for a point (or a whole city). A review-only city
    (R19) exists only for its review accounts: anyone else gets "not served" there
    (a point) or 404 (its code)."""
    if city is None and (lat is None or lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Give lat and lng, or a city code")
    from core_api.modules.markets.service import review
    from shared.redis import get_redis

    hidden = await review.hidden_for(db, viewer)
    if hidden.city(city):  # before the cache: a review account's cached answer is never anyone else's
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    # A review account's answers are never cached (R20): they must never reach anyone else, and a review city
    # made again (new kitchen ids) must not be answered with the old one's kitchens. A handful of requests.
    if hidden.sees_review:
        return await _discover(db, lat, lng, city, hide=hidden.codes, fresh=True)
    # R22: the key carries the database's cache versions (shared/cache_versions.py), so an edit to
    # any kitchen, menu, hours, rule or market is shown by the next request, not after CACHE_SECONDS;
    # the time still matters (open now, offers' hours). The JSON is sent as stored (no re-parsing).
    from shared import cache_versions as cv

    ver = ".".join(map(str, await cv.versions(db, FACT_SCOPES))) if cv.enabled() else "off"
    key = f"discover:{ver}:{city or f'{lat:.4f},{lng:.4f}'}"
    r = await get_redis()
    cached = await r.get(key)
    if cached:
        return Response(cached.encode() if isinstance(cached, str) else cached, media_type="application/json")  # type: ignore[return-value]
    out = await _discover(db, lat, lng, city, hide=hidden.codes)
    body = out.model_dump_json()
    if not cv.wrote(db):
        await r.set(key, body, ex=CACHE_SECONDS)
    return Response(body.encode(), media_type="application/json")  # type: ignore[return-value]


FACT_SCOPES = ("kitchens", "kitchen:*", "rules", "markets")


async def _discover(db: AsyncSession, lat: float | None, lng: float | None, city_code: str | None,
                    hide: frozenset[str] = frozenset(), fresh: bool = False) -> Discover:
    from core_api.modules.markets.api.v1.public import public_status, slugify
    from core_api.modules.markets.models import City, Country, Region
    from core_api.modules.markets.service.markets import MarketService
    from core_api.modules.pricing.service.engine import CartLine, NotDeliverable, QuoteInputs, compute

    zone_id = zone_name = None
    if city_code is None:
        loc = await MarketService(db).locate(lat, lng, hide=hide)  # type: ignore[arg-type]
        if not loc.serviceable:
            return Discover(served=False, reason=loc.reason,
                            city={"code": loc.city_code, "name": loc.city_name} if loc.city_code else None)
        city_code, zone_id, zone_name = loc.city_code, loc.zone_id, loc.zone_name
    row = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                            .join(Country, Country.id == City.country_id).where(City.code == city_code))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    city, region, country = row
    st = public_status(country, region, city, show_review=city.code not in hide)
    if st is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    city_path = f"/{country.code.lower()}/{slugify(city.name)}"
    base = Discover(served=st == "live" and (zone_id is not None or lat is None), country=country.code,
                    currency=country.currency, distance_unit=country.distance_unit,
                    timezone=city.timezone or region.timezone or country.timezone,
                    city={"code": city.code, "name": city.name, "path": city_path, "status": st}, zone=zone_name)
    if st != "live":
        return base

    now = datetime.now(UTC)
    tz = base.timezone or "UTC"
    from zoneinfo import ZoneInfo

    local = now.astimezone(ZoneInfo(tz))
    facts = await _city_facts(db, city, region, country, zone_id, city_path, hide, now, fresh=fresh)
    cards: list[Card] = []
    free_chip = False
    offers: dict[str, Offer] = {}
    road: dict[str, float] = {}
    if lat is not None and lng is not None:
        # R31: road distance from each restaurant to the address, in one routing call (OSRM table; falls back
        # to the straight-line estimate, logged). The delivery bands and max distance decide, not a radius.
        from shared.providers.routing import get_routing_provider

        placed = [f for f in facts.kitchens if f.k.lat is not None and f.k.lng is not None]
        legs = get_routing_provider().legs_to([(f.k.lat, f.k.lng) for f in placed], (lat, lng))
        road = {str(f.k.id): leg.distance_km for f, leg in zip(placed, legs, strict=True)}
    for f in facts.kitchens:
        k = f.k
        distance_km = None
        deliverable = True
        if lat is not None and lng is not None:
            if str(k.id) not in road:
                continue
            distance_km = road[str(k.id)]
        for o in f.offers:
            offers.setdefault(o.id, o)
        fee = None
        distance = None
        if distance_km is not None:
            distance = (Decimal(str(distance_km)) / (KM_PER_MI if country.distance_unit == "mi" else 1)).quantize(Decimal("0.01"))
            food = max(Decimal(k.minimum_order_amount or 0), Decimal("1"))
            try:
                q = compute(QuoteInputs(currency=country.currency, lines=[CartLine("Cart", 1, food)],
                                        distance=distance, local_time=local), f.resolved)
                fee = str(sum((ln.amount for ln in q.lines if ln.code == "delivery_fee"), Decimal("0")))
            except NotDeliverable:
                deliverable = False  # R31: beyond its max distance: shown, but "too far to deliver"
        a = f.a
        created = k.created_at
        cards.append(Card(
            id=str(k.id), slug=k.slug, name=k.name, path=f"{city_path}/{k.slug}", cuisine_types=list(k.cuisine_types or []),
            tags=list(k.tags or []), area=k.area, cover_url=k.cover_url,
            photo_url=facts.shown.get(str(k.id)), logo_url=k.logo_url,
            rating=float(k.rating or 0), review_count=int(k.review_count or 0),
            rating_display=rating_display(k.rating, k.review_count),
            is_new=bool(created and created > now - timedelta(days=NEW_FOR_DAYS)), open_now=a.open_now,
            opens_at=(a.back_at.isoformat() if a.back_at else None) if a.closed_for_now
            else a.next_open_at.isoformat() if a.next_open_at and not a.open_now and not a.no_tablet else None,
            closed_for_now=a.closed_for_now, not_taking_orders=a.no_tablet,
            eta_min=k.delivery_time_min, eta_max=k.delivery_time_max,
            distance=float(distance) if distance is not None else None, delivery_fee=fee, deliverable=deliverable,
            free_delivery=f.free_delivery, offer=f.card_offer,
            pickup_enabled=bool(k.pickup_enabled), pickup_only=bool(k.pickup_enabled) and not deliverable,
            pickup_fee_percent=f.pickup_fee_percent if k.pickup_enabled else None,
            minimum_order=str(k.minimum_order_amount) if k.minimum_order_amount else None))
        free_chip = free_chip or f.free_delivery_by_restaurant
    cards.sort(key=list_order)
    cuisines: dict[str, int] = {}
    for c in cards:
        for name in c.cuisine_types:
            cuisines[name] = cuisines.get(name, 0) + 1
    names = [n for n, v in sorted(cuisines.items(), key=lambda kv: (-kv[1], kv[0])) if v >= MIN_KITCHENS_PER_CUISINE]
    photos = pick_cuisine_photos(names, _photo_candidates(names, facts.everyone, {c.id for c in cards},
                                                          facts.dish_photos))
    base.restaurants = cards
    base.free_delivery_chip = free_chip
    base.cuisines = [{"name": n, "count": cuisines[n], **({"photo": photos[n]} if n in photos else {})} for n in names]
    base.offers = sorted(offers.values(), key=lambda o: (o.restaurant is not None, o.title))
    return base


def _photo_candidates(names: list[str], kitchens: list, on_cards: set[str],  # type: ignore[type-arg]
                      by_kitchen: dict[str, list[str]]) -> dict[str, list[str]]:
    """Each cuisine's photos, best first: covers of the city's kitchens of that
    cuisine that aren't on a card in this response, then the food library's photo
    of that cuisine (R8: catalog.service.photos, e.g. Japanese -> sushi, so every
    mapped cuisine has a fitting photo even when its kitchens have none), then
    dish photos from the cuisine's kitchens (``by_kitchen``: _dish_photos), then
    covers that are already on a card (repeats a card)."""
    if not names:
        return {}
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


# What a city's (or a zone's) kitchens look like apart from the address: their availability,
# the rules that apply to them, their offers and photos. R21 load test: computing this took
# about six queries per kitchen on every uncached address (130 for Boise's 21 kitchens), and
# at a 3x Boise rush core_api spent its one CPU on it and timed out everywhere. Now it's
# computed once per city and zone per FACTS_SECONDS in each process, and each address only
# adds distances and delivery fees (no queries). Answers stay as fresh as the per-address
# cache already allowed (CACHE_SECONDS). Review accounts (R20) always get fresh facts.
_facts: dict[tuple, tuple[float, "_Facts"]] = {}


@dataclass(frozen=True)
class _KitchenFacts:
    k: SimpleNamespace  # the restaurant's fields a card needs (a snapshot, not the ORM object)
    a: object  # menu.Availability
    resolved: dict  # rules that apply (pricing.engine.compute's input)
    offers: list  # [Offer], best first
    card_offer: Offer | None
    free_delivery: bool
    free_delivery_by_restaurant: bool = False  # R36: a free-delivery offer the restaurant pays for
    pickup_fee_percent: str | None = None  # R36: the pickup platform fee percent


@dataclass(frozen=True)
class _Facts:
    kitchens: list  # [_KitchenFacts], listed kitchens only
    everyone: list  # every active kitchen in the city (snapshots), for the cuisine photos
    shown: dict  # kitchen id -> photo_url
    dish_photos: dict  # kitchen id -> dish photo urls


async def _city_facts(db: AsyncSession, city, region, country, zone_id, city_path: str,  # type: ignore[no-untyped-def]
                      hide: frozenset[str], now: datetime, fresh: bool = False) -> _Facts:
    import time

    from shared.config import get_settings

    from shared import cache_versions as cv

    keep = 0.0 if fresh else get_settings().catalog.DISCOVER_FACTS_SECONDS
    # R22: and never past an edit to a kitchen, rule or market (the database's cache versions).
    ver = await cv.versions(db, FACT_SCOPES) if keep > 0 and cv.enabled() else ()
    key = (city.code, str(zone_id) if zone_id else None, hide, ver)
    hit = _facts.get(key)
    if keep > 0 and hit and time.monotonic() - hit[0] < keep:
        return hit[1]
    out = await _compute_facts(db, city, region, country, zone_id, city_path, now)
    if keep > 0 and not cv.wrote(db):
        if len(_facts) > 256:
            _facts.clear()  # old versions' entries
        _facts[key] = (time.monotonic(), out)
    return out


async def _compute_facts(db: AsyncSession, city, region, country, zone_id, city_path: str,  # type: ignore[no-untyped-def]
                         now: datetime) -> _Facts:
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service import menu as menu_svc
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    rows = (await db.execute(select(Restaurant).where(
        Restaurant.country == country.code, Restaurant.city.ilike(city.name), Restaurant.status == "active",
        Restaurant.is_active.is_(True), Restaurant.deleted_at.is_(None)))).scalars().all()
    rules_svc = RuleService(db)
    shown = await photos_for(db, rows)
    dish_photos = await _dish_photos(db, [k.id for k in rows])
    everyone = {k.id: SimpleNamespace(
        id=k.id, slug=k.slug, name=k.name, lat=k.lat, lng=k.lng, delivery_radius_km=k.delivery_radius_km,
        minimum_order_amount=k.minimum_order_amount, cuisine_types=list(k.cuisine_types or []), tags=list(k.tags or []),
        pickup_enabled=bool(getattr(k, "pickup_enabled", False)),
        area=(k.address or {}).get("landmark") if isinstance(k.address, dict) else None, cover_url=k.cover_url,
        logo_url=k.logo_url, rating=k.rating, review_count=getattr(k, "review_count", 0) or 0,
        created_at=getattr(k, "created_at", None), delivery_time_min=k.delivery_time_min, delivery_time_max=k.delivery_time_max)
        for k in rows}
    kitchens: list[_KitchenFacts] = []
    for k in rows:
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
        offers = [_offer(c, ref if c.scope_level == "restaurant" else None)
                  for c in sorted(promos, key=lambda c: (c.scope_level != "restaurant", c.template != "free_delivery"))]
        pf = resolved.get("fee:pickup_platform_fee_pct") or resolved.get("fee:platform_fee_pct")
        pct = Decimal(str(pf.params["percent"])).normalize() if pf and pf.params.get("percent") is not None else None
        kitchens.append(_KitchenFacts(k=everyone[k.id], a=a, resolved=resolved, offers=offers, card_offer=offers[0] if offers else None,
                                      free_delivery=any(c.template == "free_delivery" for c in promos),
                                      free_delivery_by_restaurant=any(c.template == "free_delivery"
                                                                      and c.params.get("funded_by") == "restaurant" for c in promos),
                                      pickup_fee_percent=f"{pct:f}" if pct is not None else None))
    return _Facts(kitchens=kitchens, everyone=list(everyone.values()), shown=shown, dish_photos=dish_photos)


async def _dish_photos(db: AsyncSession, ids: list) -> dict[str, list[str]]:  # type: ignore[type-arg]
    """Each kitchen's available dish photos, in menu order."""
    from core_api.modules.catalog.models.menu import MenuItem

    by_kitchen: dict[str, list[str]] = {}
    if ids:
        rows = (await db.execute(
            select(MenuItem.restaurant_id, MenuItem.image_url)
            .where(MenuItem.restaurant_id.in_(ids), MenuItem.image_url.is_not(None), MenuItem.image_url != "",
                   MenuItem.deleted_at.is_(None), MenuItem.is_available.is_(True))
            .order_by(MenuItem.restaurant_id, MenuItem.sort_order, MenuItem.name))).all()
        for rid, url in rows:
            by_kitchen.setdefault(str(rid), []).append(url)
    return by_kitchen


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
