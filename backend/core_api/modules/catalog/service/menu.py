"""Menu modifiers, store hours, sold-out-today, prep time and FSSAI (P10).

Other modules (pricing, orders) call ``availability`` and ``item_groups``;
they never read these tables.
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.menu import MenuItem
from core_api.modules.catalog.models.options import MenuItemOptionGroup, Option, OptionGroup, StoreHours, StoreHoursOverride
from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service import hours as H

logger = structlog.get_logger(__name__)

COUNTRY_TZ = {"IN": "Asia/Kolkata", "US": "America/New_York"}
FSSAI_EXPIRED = "fssai_expired"


class MenuError(ValueError):
    """Shown to the partner or admin as is."""


@dataclass
class Availability:
    restaurant_id: str
    listed: bool  # customers can see it (not paused for a licence or by an admin)
    open_now: bool  # can take an order right now
    reason: str | None  # why not, in plain words
    next_open_at: datetime | None
    local_time: datetime
    timezone: str
    city_code: str | None
    paused_reason: str | None


async def restaurant_market(db: AsyncSession, r: Restaurant) -> tuple[str | None, ZoneInfo, dict | None, bool]:
    """(city code, timezone, city service hours, FSSAI required) for a restaurant."""
    from core_api.modules.catalog.service.lookup import restaurant_city_code
    from core_api.modules.markets.models import City, Country, Region
    from core_api.modules.markets.service.markets import MarketService

    code = await restaurant_city_code(db, r.id)
    markets = MarketService(db)
    country = await markets.repo.country(r.country)
    fssai = bool(country and (country.settings or {}).get("fssai_required"))
    if code is None:
        return None, ZoneInfo(country.timezone if country else COUNTRY_TZ.get(r.country, "UTC")), None, fssai
    city: City | None = await markets.repo.city(code)
    assert city is not None
    region = await db.get(Region, city.region_id)
    country_row = await db.get(Country, city.country_id)
    tz = city.timezone or (region.timezone if region else None) or (country_row.timezone if country_row else "UTC")
    return code, ZoneInfo(tz), city.service_hours, fssai


def licence_problem(r: Restaurant, today: date, fssai_required: bool) -> str | None:
    if not fssai_required:
        return None
    if not r.fssai_number or not r.fssai_expires_on:
        return "FSSAI licence missing"
    if r.fssai_expires_on < today:
        return "FSSAI licence expired"
    return None


async def _hours(db: AsyncSession, restaurant_id: uuid.UUID) -> tuple[list[H.Range], dict[date, H.Override]]:
    weekly = [H.Range(h.weekday, h.opens, h.closes) for h in
              (await db.execute(select(StoreHours).where(StoreHours.restaurant_id == restaurant_id))).scalars()]
    overrides = {o.day: H.Override(o.day, o.closed, o.opens, o.closes, o.note) for o in
                 (await db.execute(select(StoreHoursOverride).where(StoreHoursOverride.restaurant_id == restaurant_id))).scalars()}
    return weekly, overrides


def paused_by_kitchen(r: Restaurant, now: datetime) -> bool:
    """"Pause orders" on the tablet (P19): until paused_until, or until resumed when it has none."""
    return not r.is_open and (r.paused_until is None or r.paused_until > now)


def busy_minutes(r: Restaurant, now: datetime) -> int:
    """"Busy? Add 10 min": extra prep minutes while it lasts."""
    return r.busy_extra_minutes if r.busy_until and r.busy_until > now else 0


async def availability(db: AsyncSession, restaurant_id: uuid.UUID, now: datetime | None = None) -> Availability:
    r = await db.get(Restaurant, restaurant_id)
    if r is None or r.deleted_at is not None:
        raise MenuError("Restaurant not found")
    code, tz, service_hours, fssai = await restaurant_market(db, r)
    local = (now or datetime.now(UTC)).astimezone(tz)
    weekly, overrides = await _hours(db, r.id)
    paused = r.paused_reason or licence_problem(r, local.date(), fssai)
    nxt = H.next_open(local, weekly, overrides) if weekly or overrides else None
    if not r.is_active:
        reason = "Not taking orders"
    elif paused:
        reason = "Temporarily unavailable"
    elif paused_by_kitchen(r, local):
        reason = "Paused by the restaurant"
    elif (weekly or overrides) and not H.is_open(local, weekly, overrides):
        o = overrides.get(local.date())
        reason = (f"Closed today: {o.note}" if o and o.closed and o.note else "Closed now") + (
            f" · opens {nxt.strftime('%a %H:%M')}" if nxt else "")
    elif not H.within_service_hours(local, service_hours):
        reason = f"Deliveries run {service_hours['open']}–{service_hours['close']}"  # type: ignore[index]
    else:
        reason = None
    return Availability(
        restaurant_id=str(r.id), listed=r.is_active and not paused, open_now=reason is None, reason=reason,
        next_open_at=nxt.replace(tzinfo=tz) if nxt else None, local_time=local, timezone=str(tz), city_code=code,
        paused_reason=r.paused_reason or (FSSAI_EXPIRED if licence_problem(r, local.date(), fssai) else None),
    )


# ── option groups ─────────────────────────────────────────────────────────────

async def groups_for_items(db: AsyncSession, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[OptionGroup]]:
    if not item_ids:
        return {}
    rows = (await db.execute(
        select(MenuItemOptionGroup.menu_item_id, OptionGroup)
        .join(OptionGroup, OptionGroup.id == MenuItemOptionGroup.group_id)
        .where(MenuItemOptionGroup.menu_item_id.in_(item_ids))
        .order_by(MenuItemOptionGroup.sort_order)
    )).all()
    out: dict[uuid.UUID, list[OptionGroup]] = {}
    for item_id, group in rows:
        out.setdefault(item_id, []).append(group)
    return out


def group_out(g: OptionGroup) -> dict:
    return {
        "id": str(g.id), "name": g.name, "min_picks": g.min_picks, "max_picks": g.max_picks,
        "options": [{"id": str(o.id), "name": o.name, "price": str(o.price), "is_default": o.is_default,
                     "is_available": o.is_available} for o in g.options],
    }


def legacy_customizations(groups: list[OptionGroup]) -> list[dict]:
    """The pre-P10 ``customizations`` shape, for apps that still read it."""
    return [
        {"id": str(g.id), "name": g.name, "required": g.min_picks > 0, "max": g.max_picks,
         "options": [{"id": str(o.id), "name": o.name, "price": float(o.price)} for o in g.options if o.is_available]}
        for g in groups
    ]


async def create_group(db: AsyncSession, restaurant_id: uuid.UUID, name: str, min_picks: int, max_picks: int,
                       options: list[dict], sort_order: int = 0) -> OptionGroup:
    _check_picks(min_picks, max_picks, len(options))
    g = OptionGroup(restaurant_id=restaurant_id, name=name, min_picks=min_picks, max_picks=max_picks, sort_order=sort_order,
                    options=[Option(name=o["name"], price=Decimal(str(o.get("price", 0))), is_default=o.get("is_default", False),
                                    is_available=o.get("is_available", True), sort_order=i) for i, o in enumerate(options)])
    db.add(g)
    await db.flush()
    return g


async def replace_group(db: AsyncSession, g: OptionGroup, name: str, min_picks: int, max_picks: int, options: list[dict]) -> OptionGroup:
    """Update a group; options keep their ids when the id is sent back."""
    _check_picks(min_picks, max_picks, len(options))
    g.name, g.min_picks, g.max_picks = name, min_picks, max_picks
    by_id = {str(o.id): o for o in g.options}
    kept: list[Option] = []
    for i, o in enumerate(options):
        row = by_id.get(str(o.get("id"))) if o.get("id") else None
        if row is None:
            row = Option(group_id=g.id)
        row.name, row.price, row.sort_order = o["name"], Decimal(str(o.get("price", 0))), i
        row.is_default, row.is_available = o.get("is_default", False), o.get("is_available", True)
        kept.append(row)
    g.options = kept
    await db.flush()
    return g


def _check_picks(min_picks: int, max_picks: int, n: int) -> None:
    if n == 0:
        raise MenuError("A group needs at least one option")
    if not (0 <= min_picks <= max_picks):
        raise MenuError("Pick counts: 0 ≤ minimum ≤ maximum")
    if min_picks > n:
        raise MenuError("The minimum is more than the number of options")


async def set_item_groups(db: AsyncSession, item: MenuItem, group_ids: list[uuid.UUID]) -> None:
    groups = (await db.execute(select(OptionGroup).where(OptionGroup.id.in_(group_ids)))).scalars().all()
    if len(groups) != len(set(group_ids)) or any(g.restaurant_id != item.restaurant_id for g in groups):
        raise MenuError("Every group must belong to this restaurant")
    await db.execute(delete(MenuItemOptionGroup).where(MenuItemOptionGroup.menu_item_id == item.id))
    for i, gid in enumerate(group_ids):
        db.add(MenuItemOptionGroup(menu_item_id=item.id, group_id=gid, sort_order=i))
    await db.flush()


async def groups_from_legacy(db: AsyncSession, item: MenuItem, customizations: list[dict]) -> None:
    """Accept the old ``customizations`` list on item create/update."""
    ids = []
    for i, c in enumerate(customizations):
        g = await create_group(db, item.restaurant_id, c["name"], 1 if c.get("required") else 0, int(c.get("max", 1)),
                               c.get("options", []), sort_order=i)
        ids.append(g.id)
    await set_item_groups(db, item, ids)


# ── sold out, prep time, licence ──────────────────────────────────────────────

async def set_sold_out_today(db: AsyncSession, item: MenuItem, sold_out: bool, now: datetime | None = None) -> MenuItem:
    r = await db.get(Restaurant, item.restaurant_id)
    assert r is not None
    _, tz, _, _ = await restaurant_market(db, r)
    local = (now or datetime.now(UTC)).astimezone(tz)
    item.sold_out_until = H.end_of_local_day(local) if sold_out else None
    await db.flush()
    return item


def is_sold_out(item: MenuItem, now: datetime | None = None) -> bool:
    return item.sold_out_until is not None and item.sold_out_until > (now or datetime.now(UTC))


async def set_licence(db: AsyncSession, r: Restaurant, number: str, expires_on: date, today: date) -> Restaurant:
    if not (number.isdigit() and len(number) == 14):
        raise MenuError("An FSSAI licence number has 14 digits")
    r.fssai_number, r.fssai_expires_on = number, expires_on
    if r.paused_reason == FSSAI_EXPIRED and expires_on >= today:
        r.paused_reason = None  # renewed: listed again
        logger.info("restaurant_relisted_after_licence", restaurant_id=str(r.id))
    await db.flush()
    await _forget_cached_listings()
    return r


async def _forget_cached_listings() -> None:
    from core_api.modules.catalog.repository.cache import cache_delete_pattern

    try:
        await cache_delete_pattern("restaurants:*")
    except Exception as e:  # noqa: BLE001 - the cache expires on its own
        logger.warning("listing_cache_clear_failed", error=str(e))


async def pause_expired_licences(db: AsyncSession, today: date) -> list[uuid.UUID]:
    """Pause every Indian listing whose FSSAI licence ran out (idempotent)."""
    from core_api.modules.markets.models import Country

    countries = [c.code for c in (await db.execute(select(Country))).scalars() if (c.settings or {}).get("fssai_required")]
    if not countries:
        return []
    q = (
        update(Restaurant)
        .where(Restaurant.country.in_(countries), Restaurant.paused_reason.is_(None), Restaurant.deleted_at.is_(None),
               (Restaurant.fssai_expires_on < today) | Restaurant.fssai_expires_on.is_(None))
        .values(paused_reason=FSSAI_EXPIRED)
        .returning(Restaurant.id)
    )
    paused = list((await db.execute(q)).scalars())
    for rid in paused:
        logger.warning("restaurant_paused_licence_expired", restaurant_id=str(rid))
    if paused:
        await _forget_cached_listings()
    return paused


async def set_hours(db: AsyncSession, restaurant_id: uuid.UUID, weekly: list[dict]) -> None:
    await db.execute(delete(StoreHours).where(StoreHours.restaurant_id == restaurant_id))
    for h in weekly:
        if h["opens"] == h["closes"]:
            raise MenuError("Opening and closing time can't be the same")
        db.add(StoreHours(restaurant_id=restaurant_id, weekday=h["weekday"], opens=h["opens"], closes=h["closes"]))
    await db.flush()


async def set_override(db: AsyncSession, restaurant_id: uuid.UUID, day: date, closed: bool, opens, closes, note) -> None:  # type: ignore[no-untyped-def]
    if not closed and (opens is None or closes is None):
        raise MenuError("Give opening and closing times, or mark the day closed")
    existing = (await db.execute(select(StoreHoursOverride).where(
        StoreHoursOverride.restaurant_id == restaurant_id, StoreHoursOverride.day == day))).scalar_one_or_none()
    row = existing or StoreHoursOverride(restaurant_id=restaurant_id, day=day)
    row.closed, row.opens, row.closes, row.note = closed, None if closed else opens, None if closed else closes, note
    if existing is None:
        db.add(row)
    await db.flush()
