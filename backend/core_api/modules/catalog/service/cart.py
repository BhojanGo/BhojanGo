"""Price a cart against the live menu (used by the quote engine, P8).

Items are chosen by id; modifiers by option-group and option name, matching
the menu item's ``customizations`` (P10 turns these into proper option groups
with ids and min/max picks).
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.menu import MenuItem
from core_api.modules.catalog.models.restaurant import Restaurant


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


async def price_cart(db: AsyncSession, restaurant_id: uuid.UUID, items: list[dict]) -> tuple[RestaurantInfo, list[PricedLine]]:
    """``items``: [{"menu_item_id", "quantity", "options": [{"group", "option"}]}]."""
    r = await db.get(Restaurant, restaurant_id)
    if r is None or not r.is_active or r.deleted_at is not None:
        raise CartError("This restaurant isn't taking orders")
    ids = [uuid.UUID(str(i["menu_item_id"])) for i in items]
    rows = (await db.execute(select(MenuItem).where(MenuItem.id.in_(ids)))).scalars()
    menu = {m.id: m for m in rows}

    lines: list[PricedLine] = []
    for raw in items:
        m = menu.get(uuid.UUID(str(raw["menu_item_id"])))
        if m is None or m.restaurant_id != r.id or m.deleted_at is not None:
            raise CartError("An item in your bag is no longer on the menu")
        if not m.is_available:
            raise CartError(f"{m.name} is sold out")
        chosen: dict[str, list[str]] = {}
        for o in raw.get("options", []):
            chosen.setdefault(o["group"], []).append(o["option"])
        groups = {g["name"]: g for g in (m.customizations or [])}
        unknown = set(chosen) - set(groups)
        if unknown:
            raise CartError(f"{m.name} has no option {sorted(unknown)[0]!r}")
        price = Decimal(m.price)
        labels: list[str] = []
        for name, g in groups.items():
            picks = chosen.get(name, [])
            if g.get("required") and not picks:
                raise CartError(f"Choose {name.lower()} for {m.name}")
            if len(picks) > int(g.get("max", 1)):
                raise CartError(f"Pick at most {g.get('max', 1)} for {name.lower()}")
            options = {o["name"]: o for o in g.get("options", [])}
            for pick in picks:
                if pick not in options:
                    raise CartError(f"{pick!r} isn't an option for {m.name}")
                price += Decimal(str(options[pick].get("price", 0)))
                labels.append(pick)
        qty = int(raw["quantity"])
        if not 1 <= qty <= 50:
            raise CartError("Quantity must be between 1 and 50")
        lines.append(PricedLine(str(m.id), m.name, qty, price, tuple(labels)))

    info = RestaurantInfo(
        id=str(r.id), name=r.name, lat=r.lat, lng=r.lng, currency=r.currency, country=r.country,
        tier=None, prep_minutes=r.avg_prep_minutes,
    )
    return info, lines
