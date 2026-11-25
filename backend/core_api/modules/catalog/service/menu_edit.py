"""R43: menu editing rules, dish and category schedules, and the menu's history.

Price rules (``price_problem``): more than 0 (an option may be 0); at most 2 decimals; whole rupees in INR.
A price changed by more than 50% (``big_change``) needs the editor to confirm it (PRICE_CONFIRM).

A schedule is two local times: served from ``available_from`` until ``available_until``; an end at or before
the start runs past midnight (22:00-02:00). A dish outside its own or its category's schedule stays on the menu,
marked "Available 7:00 am - 11:00 am", and can't be ordered (the quote refuses it).

Every change goes to ``menu_changes`` (who, when, each field's old and new value).
"""
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.menu import MenuCategory, MenuChange, MenuItem
from core_api.modules.catalog.models.restaurant import Restaurant
from shared.auth import CurrentUser

BIG_CHANGE = Decimal("0.5")  # more than 50% up or down: the editor confirms
SPICE_LEVELS = (0, 1, 2, 3)  # none, mild, medium, hot
WHOLE_UNIT_CURRENCIES = {"INR"}

# What the history records for a dish and a category, in this order.
DISH_FIELDS = ("name", "description", "price", "image_url", "category", "is_veg", "spice_level", "is_available",
               "available_from", "available_until")
CATEGORY_FIELDS = ("name", "is_active", "available_from", "available_until")


class RuleError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


# ── prices ────────────────────────────────────────────────────────────────────

def price_problem(price: Decimal, currency: str, *, allow_zero: bool = False) -> str | None:
    """Why this price can't be used, in plain words; None when it's fine."""
    p = Decimal(str(price))
    if p < 0 or (p == 0 and not allow_zero):
        return "The price must be more than 0" if not allow_zero else "The price can't be below 0"
    if currency.upper() in WHOLE_UNIT_CURRENCIES:
        if p != p.to_integral_value():
            return "Prices in rupees are whole numbers (₹120, not ₹120.50)"
    elif p.normalize().as_tuple().exponent < -2:  # type: ignore[operator]
        return "A price has at most 2 decimals (12.99)"
    return None


def check_price(price: Decimal, currency: str, *, allow_zero: bool = False) -> None:
    problem = price_problem(price, currency, allow_zero=allow_zero)
    if problem:
        raise RuleError("PRICE_RULE", problem)


def big_change(old: Decimal, new: Decimal) -> bool:
    old, new = Decimal(str(old)), Decimal(str(new))
    return old > 0 and abs(new - old) / old > BIG_CHANGE


def confirm_needed(old: Decimal, new: Decimal, confirmed: bool) -> None:
    if big_change(old, new) and not confirmed:
        pct = int((abs(Decimal(str(new)) - Decimal(str(old))) / Decimal(str(old)) * 100).to_integral_value())
        raise RuleError("PRICE_CONFIRM", f"The price changes by {pct}% ({old} to {new}). Confirm to save it.",
                        {"old": f"{Decimal(str(old)):.2f}", "new": f"{Decimal(str(new)):.2f}", "percent": pct})


# ── schedules ─────────────────────────────────────────────────────────────────

def check_window(start: time | None, end: time | None) -> None:
    if (start is None) != (end is None):
        raise RuleError("SCHEDULE_RULE", "Set both times (from and until), or neither")
    if start is not None and start == end:
        raise RuleError("SCHEDULE_RULE", "From and until can't be the same time")


def in_window(start: time | None, end: time | None, t: time) -> bool:
    if start is None or end is None:
        return True
    if start < end:
        return start <= t < end
    return t >= start or t < end  # runs past midnight


def served_now(item: MenuItem, category: MenuCategory | None, local: datetime) -> bool:
    t = local.time().replace(tzinfo=None)
    return in_window(item.available_from, item.available_until, t) and (
        category is None or in_window(category.available_from, category.available_until, t))


def schedule_of(item: MenuItem, category: MenuCategory | None) -> dict | None:
    """The window that limits the dish (its own first, else its category's), as "HH:MM"."""
    for src in (item, category):
        if src is not None and src.available_from is not None and src.available_until is not None:
            return {"from": src.available_from.strftime("%H:%M"), "until": src.available_until.strftime("%H:%M")}
    return None


def seconds_to_next_edge(windows: list[tuple[time, time]], local: datetime) -> float | None:
    """Seconds until the next schedule start or end (a cached menu is kept no longer than that)."""
    best: float | None = None
    for start, end in windows:
        for edge in (start, end):
            at = local.replace(hour=edge.hour, minute=edge.minute, second=0, microsecond=0)
            if at <= local:
                at += timedelta(days=1)
            s = (at - local).total_seconds()
            best = s if best is None else min(best, s)
    return best


# ── history ───────────────────────────────────────────────────────────────────

def _plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    if isinstance(v, time):
        return v.strftime("%H:%M")
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict:
    return {f: _plain(getattr(obj, f)) for f in fields}


def diff(before: dict, after: dict) -> list[dict]:
    return [{"field": k, "old": before.get(k), "new": after.get(k)} for k in after if before.get(k) != after.get(k)]


async def record(db: AsyncSession, r: Restaurant, user: CurrentUser, *, entity: str, entity_id: uuid.UUID | None,
                 name: str, action: str, changes: list[dict] | None = None) -> MenuChange | None:
    """One row in the history. A "changed" with nothing changed records nothing."""
    if action == "changed" and not changes:
        return None
    row = MenuChange(restaurant_id=r.id, actor_id=user.id, actor_name=user.email or "",
                     actor_kind="restaurant" if r.owner_id == user.id else "admin",
                     entity=entity, entity_id=entity_id, entity_name=name[:255], action=action, changes=changes or [])
    db.add(row)
    await db.flush()
    return row


async def history(db: AsyncSession, restaurant_id: uuid.UUID, *, limit: int = 50, before: datetime | None = None,
                  entity_id: uuid.UUID | None = None) -> list[MenuChange]:
    q = select(MenuChange).where(MenuChange.restaurant_id == restaurant_id)
    if before is not None:
        q = q.where(MenuChange.at < before)
    if entity_id is not None:
        q = q.where(MenuChange.entity_id == entity_id)
    return list((await db.execute(q.order_by(MenuChange.at.desc(), MenuChange.id).limit(limit))).scalars())


def change_out(c: MenuChange, viewer_is_admin: bool, viewer_id: uuid.UUID) -> dict:
    """Admins see who (their email); the restaurant sees "You" or "BhojanGo" (an admin's change)."""
    if viewer_is_admin:
        who = c.actor_name or c.actor_kind
    else:
        who = "you" if c.actor_id == viewer_id else "bhojango"
    return {"id": str(c.id), "at": c.at.isoformat(), "who": who, "actor_kind": c.actor_kind, "entity": c.entity,
            "entity_id": str(c.entity_id) if c.entity_id else None, "name": c.entity_name, "action": c.action,
            "changes": c.changes}
