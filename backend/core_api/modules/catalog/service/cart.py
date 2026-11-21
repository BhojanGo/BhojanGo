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


# ── "Order again" (R27) ────────────────────────────────────────────────────────
#
# R26: "Order again" on a delivered order failed with "We couldn't add this order to your bag".
# A past line is matched against today's menu here, without the database (unit-tested), then priced:
#   - an item gone from the menu or sold out is left out and named ("Butter Croissant is sold out");
#   - an option no longer offered (removed, or unavailable today) is dropped and named ("Oat is no
#     longer offered"); the item is still added. A choice the item needs (min picks) that lost its
#     option gets the group's default, so the item can still be ordered;
#   - options are found by name (orders keep the names), also as {"group", "option"|"name"} from older
#     orders, ignoring case and spaces; the same name in two groups goes to the first group that has room.


@dataclass(frozen=True)
class ReorderProblem:
    item: str
    reason: str  # sold_out | removed | option_gone | unavailable
    option: str | None = None
    detail: str | None = None  # the quote's own words for "unavailable"


def _norm(s: object) -> str:
    return " ".join(str(s or "").split()).casefold()


def _labels(raw: dict) -> list[str]:
    out = []
    for o in raw.get("options") or []:
        if isinstance(o, dict):
            o = o.get("name") or o.get("option") or ""
        if str(o).strip():
            out.append(str(o))
    return out


def plan_line(raw: dict, item, groups: list, restaurant_id: uuid.UUID,  # type: ignore[no-untyped-def]
              now: datetime | None = None) -> tuple[list[dict] | None, list[ReorderProblem]]:
    """A past order line against today's menu: (picks for the quote, or None when the item can't be
    ordered; what changed). ``item``: the MenuItem (None when gone); ``groups``: its option groups."""
    name = str(raw.get("name") or getattr(item, "name", None) or "An item")
    if item is None or item.deleted_at is not None or item.restaurant_id != restaurant_id:
        return None, [ReorderProblem(name, "removed")]
    name = item.name
    if not item.is_available or is_sold_out(item, now):
        return None, [ReorderProblem(name, "sold_out")]
    problems: list[ReorderProblem] = []
    chosen: dict[uuid.UUID, list] = {g.id: [] for g in groups}
    for label in _labels(raw):
        found = [(g, o) for g in groups for o in g.options if _norm(o.name) == _norm(label)]
        room = [(g, o) for g, o in found if len(chosen[g.id]) < g.max_picks and o not in chosen[g.id]]
        g_o = room[0] if room else (found[0] if found else None)
        if g_o is None or not g_o[1].is_available:
            problems.append(ReorderProblem(name, "option_gone", option=label))
            continue
        g, o = g_o
        if o not in chosen[g.id] and len(chosen[g.id]) < g.max_picks:
            chosen[g.id].append(o)
    for g in groups:  # a choice the item needs: the default (or the first available) option
        while len(chosen[g.id]) < g.min_picks:
            spare = [o for o in g.options if o.is_available and o not in chosen[g.id]]
            pick = next((o for o in spare if o.is_default), spare[0] if spare else None)
            if pick is None:
                return None, [*problems, ReorderProblem(name, "unavailable")]
            chosen[g.id].append(pick)
    picks = [{"group": str(g.id), "option": str(o.id), "name": o.name} for g in groups for o in chosen[g.id]]
    return picks, problems


async def reorder_lines(db: AsyncSession, restaurant_id: uuid.UUID, past: list[dict],
                        now: datetime | None = None) -> tuple[list[dict], list[str], list[ReorderProblem]]:
    """A past order's lines against today's menu, for "Order again": each line that can still be
    ordered, at today's price, with its options as picks the quote accepts; the names of the items
    that can't; and every change (an item left out, an option dropped). Opening hours aren't
    checked: the bag shows that, and the quote refuses a closed kitchen."""
    ids = []
    for raw in past:
        try:
            ids.append(uuid.UUID(str(raw.get("menu_item_id"))))
        except ValueError:
            continue
    menu = {m.id: m for m in (await db.execute(select(MenuItem).where(MenuItem.id.in_(ids)))).scalars()} if ids else {}
    groups_by_item = await groups_for_items(db, ids)
    ok: list[dict] = []
    gone: list[str] = []
    problems: list[ReorderProblem] = []
    for raw in past:
        try:
            item_id = uuid.UUID(str(raw.get("menu_item_id")))
        except ValueError:
            item_id = None
        item = menu.get(item_id) if item_id else None
        picks, changed = plan_line(raw, item, groups_by_item.get(item_id, []) if item_id else [], restaurant_id, now)
        problems += changed
        if picks is None:
            gone.append(changed[-1].item)
            continue
        try:
            qty = min(max(int(raw.get("quantity") or 1), 1), 50)
            _, lines = await price_cart(db, restaurant_id, [{"menu_item_id": item_id, "quantity": qty, "options": picks}],
                                        check_open=False, now=now)
        except CartError as e:
            gone.append(item.name)
            problems.append(ReorderProblem(item.name, "unavailable", detail=str(e)))
            continue
        line = lines[0]
        ok.append({"menu_item_id": line.item_id, "name": line.name, "quantity": line.quantity, "options": picks,
                   "price": float(line.unit_price), "available": True})
    return ok, gone, problems
