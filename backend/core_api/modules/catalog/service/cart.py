"""Price a cart against the live menu (used by the quote engine).

Items are chosen by id; options by group and option, each given as an id or a
name (the old apps send names). Since P10 the menu has real option groups with
min/max picks, sold-out-today items, and store hours.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.menu import MenuItem
from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service.menu import availability, groups_for_items, is_sold_out


class CartError(ValueError):
    """The cart doesn't match the menu; the message is shown to the customer."""


@dataclass(frozen=True)
class PricedLine:
    item_id: str
    name: str
    quantity: int
    unit_price: Decimal  # base price + chosen options
    options: tuple[str, ...]


@dataclass(frozen=True)
class RestaurantInfo:
    id: str
    name: str
    lat: float | None
    lng: float | None
    currency: str
    country: str
    tier: str | None
    prep_minutes: int


async def price_cart(db: AsyncSession, restaurant_id: uuid.UUID, items: list[dict], *,
                     check_open: bool = True, now: datetime | None = None) -> tuple[RestaurantInfo, list[PricedLine]]:
    """``items``: [{"menu_item_id", "quantity", "options": [{"group", "option"}]}].
    ``check_open=False`` prices a closed restaurant (the admin simulator)."""
    r = await db.get(Restaurant, restaurant_id)
    if r is None or not r.is_active or r.deleted_at is not None:
        raise CartError("This restaurant isn't taking orders")
    if check_open:
        avail = await availability(db, r.id, now)
        if not avail.open_now:
            raise CartError(f"{r.name}: {avail.reason}")

    ids = [uuid.UUID(str(i["menu_item_id"])) for i in items]
    menu = {m.id: m for m in (await db.execute(select(MenuItem).where(MenuItem.id.in_(ids)))).scalars()}
    groups_by_item = await groups_for_items(db, list(menu))

    lines: list[PricedLine] = []
    for raw in items:
        m = menu.get(uuid.UUID(str(raw["menu_item_id"])))
        if m is None or m.restaurant_id != r.id or m.deleted_at is not None:
            raise CartError("An item in your bag is no longer on the menu")
        if not m.is_available or is_sold_out(m, now):
            raise CartError(f"{m.name} is sold out today")
        qty = int(raw["quantity"])
        if not 1 <= qty <= 50:
            raise CartError("Quantity must be between 1 and 50")

        groups = groups_by_item.get(m.id, [])
        picks: dict[uuid.UUID, list] = {g.id: [] for g in groups}
        for pick in raw.get("options", []):
            g = next((g for g in groups if pick["group"] in (str(g.id), g.name)), None)
            if g is None:
                raise CartError(f"{m.name} has no option {pick['group']!r}")
            o = next((o for o in g.options if pick["option"] in (str(o.id), o.name)), None)
            if o is None:
                raise CartError(f"{pick['option']!r} isn't an option for {m.name}")
            if not o.is_available:
                raise CartError(f"{o.name} is unavailable today")
            picks[g.id].append(o)

        price = Decimal(m.price)
        labels: list[str] = []
        for g in groups:
            chosen = picks[g.id]
            if len(chosen) < g.min_picks:
                raise CartError(f"Choose {g.name.lower()} for {m.name}" if g.min_picks == 1
                                else f"Choose at least {g.min_picks} {g.name.lower()} for {m.name}")
            if len(chosen) > g.max_picks:
                raise CartError(f"Pick at most {g.max_picks} for {g.name.lower()}")
            if len({o.id for o in chosen}) != len(chosen):
                raise CartError(f"{g.name}: each option once")
            for o in chosen:
                price += Decimal(o.price)
                labels.append(o.name)
        lines.append(PricedLine(str(m.id), m.name, qty, price, tuple(labels)))

    info = RestaurantInfo(
        id=str(r.id), name=r.name, lat=r.lat, lng=r.lng, currency=r.currency, country=r.country,
        tier=r.tier, prep_minutes=r.avg_prep_minutes,
    )
    return info, lines
