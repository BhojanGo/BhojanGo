"""Incident tools (R17), the service: pause a kitchen, pause ordering, bulk refunds, bulk messages.

Every action: the caller has the permission for the scope (the API checks), gives a reason, has
confirmed (the API takes ``confirm: true`` only after a preview), and an audit entry is written here.
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit.service import record
from core_api.modules.incidents.models import BulkMessage, BulkRefund, OrderingPause
from shared import outbox
from shared.texts import INCIDENT_ADMIN_PARAMS, INCIDENT_FROM_ORDER, INCIDENT_MESSAGES, incident_placeholders

logger = structlog.get_logger(__name__)
MAX_ORDERS = 500  # one bulk refund
MAX_WINDOW = timedelta(days=7)
MAX_RECIPIENTS = 5000


class IncidentError(ValueError):
    """Refused, with a reason an admin can act on."""


def _now() -> datetime:
    return datetime.now(UTC)


# ── a kitchen ────────────────────────────────────────────────────────────────

async def pause_kitchen(db: AsyncSession, restaurant_id: uuid.UUID, *, reason: str, back_at: datetime | None,
                        actor_id: uuid.UUID, scope: str) -> dict:
    from core_api.modules.catalog.models.restaurant import Restaurant

    r = await db.get(Restaurant, restaurant_id)
    if r is None or r.deleted_at is not None:
        raise IncidentError("Kitchen not found")
    if back_at is not None and back_at <= _now():
        raise IncidentError("The 'back at' time has already passed")
    before = _kitchen_state(r)
    r.admin_paused_at, r.admin_paused_until, r.admin_pause_reason, r.admin_paused_by = _now(), back_at, reason, actor_id
    await record(db, actor_id=actor_id, action="kitchen.paused", entity_type="restaurant", entity_id=r.id, scope=scope,
                 before=before, after=_kitchen_state(r))
    await _forget_listings()
    return _kitchen_state(r)


async def resume_kitchen(db: AsyncSession, restaurant_id: uuid.UUID, *, reason: str, actor_id: uuid.UUID, scope: str) -> dict:
    from core_api.modules.catalog.models.restaurant import Restaurant

    r = await db.get(Restaurant, restaurant_id)
    if r is None or r.deleted_at is not None:
        raise IncidentError("Kitchen not found")
    if r.admin_paused_at is None:
        raise IncidentError("This kitchen isn't paused by an admin")
    before = _kitchen_state(r)
    r.admin_paused_at = r.admin_paused_until = r.admin_pause_reason = r.admin_paused_by = None
    await record(db, actor_id=actor_id, action="kitchen.resumed", entity_type="restaurant", entity_id=r.id, scope=scope,
                 before=before, after={**_kitchen_state(r), "reason": reason})
    await _forget_listings()
    return _kitchen_state(r)


def _kitchen_state(r) -> dict:  # type: ignore[no-untyped-def]
    return {"name": r.name, "closed_for_now": r.closed_for_now, "reason": r.admin_pause_reason,
            "paused_at": r.admin_paused_at.isoformat() if r.admin_paused_at else None,
            "back_at": r.admin_paused_until.isoformat() if r.admin_paused_until else None}


async def _forget_listings() -> None:
    try:
        from core_api.modules.catalog.repository.cache import cache_delete_pattern

        await cache_delete_pattern("restaurants:list:*")
    except Exception:  # noqa: BLE001 - a cache miss is fine; listings expire by themselves
        logger.warning("listing_cache_not_cleared")


# ── ordering pauses ──────────────────────────────────────────────────────────

def covers(scope: str, city_code: str | None) -> bool:
    """"*" covers every city; "IN" its cities; "IN-TG-HYD" itself."""
    if scope == "*":
        return True
    return bool(city_code) and (city_code == scope or city_code.startswith(scope + "-"))  # type: ignore[union-attr]


async def active_pauses(db: AsyncSession, now: datetime | None = None) -> list[OrderingPause]:
    now = now or _now()
    q = select(OrderingPause).where(OrderingPause.ended_at.is_(None),
                                    or_(OrderingPause.until.is_(None), OrderingPause.until > now)).order_by(OrderingPause.created_at)
    return list((await db.execute(q)).scalars())


async def pause_for(db: AsyncSession, city_code: str | None) -> OrderingPause | None:
    """The ordering pause that stops new orders in this city now, if any (the widest first)."""
    hits = [p for p in await active_pauses(db) if covers(p.scope, city_code)]
    return min(hits, key=lambda p: len(p.scope.replace("*", ""))) if hits else None


def pause_message(p: OrderingPause) -> str:
    """What a refused quote or order says (English; the website and apps show their own translation)."""
    where = "" if p.scope == "*" else f" in {p.area}"
    return f"Ordering{where} is paused for now while we fix a problem." + (f" {p.note}" if p.note else "")


async def area_name(db: AsyncSession, scope: str) -> str:
    from core_api.modules.markets.models import City, Country

    if scope == "*":
        return "BhojanGo"
    model = Country if len(scope) == 2 else City
    row = (await db.execute(select(model).where(model.code == scope))).scalars().first()
    if row is None:
        raise IncidentError("Pick a country or city that exists in Markets")
    return row.name


async def pause_ordering(db: AsyncSession, *, scope: str, reason: str, note: str | None, until: datetime | None,
                         actor_id: uuid.UUID) -> OrderingPause:
    if until is not None and until <= _now():
        raise IncidentError("The end time has already passed")
    if any(p.scope == scope for p in await active_pauses(db)):
        raise IncidentError("Ordering here is already paused")
    p = OrderingPause(scope=scope, area=await area_name(db, scope), reason=reason, note=note, until=until, created_by=actor_id)
    db.add(p)
    await db.flush()
    await record(db, actor_id=actor_id, action="ordering.paused", entity_type="ordering_pause", entity_id=p.id, scope=scope,
                 after=pause_out(p))
    return p


async def end_pause(db: AsyncSession, pause_id: uuid.UUID, *, reason: str, actor_id: uuid.UUID) -> OrderingPause:
    p = await db.get(OrderingPause, pause_id)
    if p is None or p.ended_at is not None:
        raise IncidentError("This pause has already ended")
    before = pause_out(p)
    p.ended_at, p.ended_by = _now(), actor_id
    await record(db, actor_id=actor_id, action="ordering.resumed", entity_type="ordering_pause", entity_id=p.id, scope=p.scope,
                 before=before, after={**pause_out(p), "reason_to_end": reason})
    return p


def pause_out(p: OrderingPause, admin: bool = True) -> dict:
    out = {"id": str(p.id), "scope": p.scope, "area": p.area, "note": p.note,
           "until": p.until.isoformat() if p.until else None}
    if admin:
        out |= {"reason": p.reason, "created_by": str(p.created_by),
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "ended_at": p.ended_at.isoformat() if p.ended_at else None}
    return out


# ── bulk refunds ─────────────────────────────────────────────────────────────

@dataclass
class RefundPick:
    market_city: str
    restaurant_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    placed_from: datetime
    placed_to: datetime
    mode: str  # full | percent
    percent: Decimal | None = None


async def select_orders(db: AsyncSession, pick: RefundPick) -> tuple[list[dict], str | None]:
    """The orders a bulk refund would touch and how much each gets back (minor units): orders placed in
    the window in the city (and kitchen or zone), with a captured payment not yet fully refunded."""
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import PaymentIntent

    if pick.placed_to <= pick.placed_from:
        raise IncidentError("The window's end must be after its start")
    if pick.placed_to - pick.placed_from > MAX_WINDOW:
        raise IncidentError("Pick a window of 7 days or less")
    if pick.mode == "percent" and not (pick.percent and Decimal(0) < pick.percent < Decimal(100)):
        raise IncidentError("A partial refund needs a percentage between 0 and 100")
    conds = [Order.market_city == pick.market_city, Order.placed_at >= pick.placed_from, Order.placed_at < pick.placed_to]
    if pick.restaurant_id:
        conds.append(Order.restaurant_id == pick.restaurant_id)
    if pick.zone_id:
        conds.append(Order.zone_id == pick.zone_id)
    rows = (await db.execute(
        select(Order, PaymentIntent).join(PaymentIntent, PaymentIntent.order_id == Order.id)
        .where(and_(*conds), PaymentIntent.status.in_(("succeeded", "partially_refunded")))
        .order_by(Order.placed_at).limit(MAX_ORDERS + 1))).all()
    if len(rows) > MAX_ORDERS:
        raise IncidentError(f"More than {MAX_ORDERS} orders: pick a narrower window, a kitchen or a zone")
    out: list[dict] = []
    currency = None
    for o, pi in rows:
        left = pi.amount - (pi.refunded_amount or 0)
        if left <= 0:
            continue
        amount = left if pick.mode == "full" else min(left, int((Decimal(pi.amount) * pick.percent / 100)  # type: ignore[operator]
                                                                 .quantize(Decimal(1), rounding=ROUND_HALF_UP)))
        if amount <= 0:
            continue
        currency = currency or pi.currency
        out.append({"order_id": str(o.id), "customer_id": str(o.customer_id), "restaurant": o.restaurant_name,
                    "status": o.status, "placed_at": o.placed_at.isoformat() if o.placed_at else None,
                    "paid": pi.amount, "amount": amount, "currency": pi.currency})
    return out, currency


# R22 security review (S12): without a total cap, a bulk refund of 500 orders each just under
# the per-order limit ran with no second admin. Unset in the rule: this many times the per-order limit.
AUTO_TOTAL_TIMES = Decimal(50)


async def auto_limit(db: AsyncSession, market_city: str) -> Decimal:
    """The city's automatic refund limit per order (business rule auto_refund_limit; 0 when none)."""
    return (await auto_limits(db, market_city))[0]


async def auto_limits(db: AsyncSession, market_city: str) -> tuple[Decimal, Decimal]:
    """(per order, whole batch) a bulk refund may reach without a second admin (business rule
    auto_refund_limit: max_per_order, max_bulk_total; the batch defaults to AUTO_TOTAL_TIMES x the per-order limit)."""
    from core_api.modules.payments.service.refunds import business_rule

    rule = await business_rule(db, market_city, "auto_refund_limit")
    params = rule.params if rule else {}
    per_order = Decimal(str(params.get("max_per_order") or 0))
    total = params.get("max_bulk_total")
    return per_order, Decimal(str(total)) if total is not None else per_order * AUTO_TOTAL_TIMES


def approval_reasons(amounts_minor: list[int], per_order: Decimal, total_cap: Decimal) -> list[str]:
    """Why a bulk refund needs a second admin (empty: it runs at once). Amounts in minor units."""
    reasons = []
    if Decimal(max(amounts_minor, default=0)) / 100 > per_order:
        reasons.append("order_over_limit")
    if Decimal(sum(amounts_minor)) / 100 > total_cap:
        reasons.append("total_over_limit")
    return reasons


async def preview_refund(db: AsyncSession, pick: RefundPick) -> dict:
    orders, currency = await select_orders(db, pick)
    limit, total_cap = await auto_limits(db, pick.market_city)
    reasons = approval_reasons([o["amount"] for o in orders], limit, total_cap)
    return {"orders": orders, "count": len(orders), "total": sum(o["amount"] for o in orders), "currency": currency,
            "auto_refund_limit": str(limit), "auto_refund_total_limit": str(total_cap),
            "needs_approval": bool(reasons), "approval_reasons": reasons}


async def create_refund(db: AsyncSession, pick: RefundPick, *, reason: str, actor_id: uuid.UUID) -> BulkRefund:
    p = await preview_refund(db, pick)
    if not p["count"]:
        raise IncidentError("No paid orders to refund in that selection")
    b = BulkRefund(market_city=pick.market_city, mode=pick.mode, percent=pick.percent, reason=reason,
                   filters={"restaurant_id": str(pick.restaurant_id) if pick.restaurant_id else None,
                            "zone_id": str(pick.zone_id) if pick.zone_id else None,
                            "placed_from": pick.placed_from.isoformat(), "placed_to": pick.placed_to.isoformat()},
                   orders=p["orders"], count=p["count"], total=p["total"], currency=p["currency"],
                   status="pending_approval" if p["needs_approval"] else "running", requested_by=actor_id, results=[])
    db.add(b)
    await db.flush()
    await record(db, actor_id=actor_id, action="bulk_refund.requested", entity_type="bulk_refund", entity_id=b.id,
                 scope=pick.market_city, after=refund_out(b, orders=False))
    if b.status == "running":
        await _execute(db, b, actor_id)
    return b


async def decide_refund(db: AsyncSession, refund_id: uuid.UUID, *, approve: bool, note: str, actor_id: uuid.UUID) -> BulkRefund:
    b = await db.get(BulkRefund, refund_id, with_for_update=True)
    if b is None or b.status != "pending_approval":
        raise IncidentError("This bulk refund isn't waiting for approval")
    if b.requested_by == actor_id:
        raise IncidentError("A second admin approves a bulk refund: not the one who asked for it")
    b.decided_by, b.decided_at, b.decision_note = actor_id, _now(), note
    await record(db, actor_id=actor_id, action="bulk_refund.approved" if approve else "bulk_refund.rejected",
                 entity_type="bulk_refund", entity_id=b.id, scope=b.market_city, after={"note": note})
    if approve:
        b.status = "running"
        await _execute(db, b, actor_id)
    else:
        b.status = "rejected"
    return b


async def _execute(db: AsyncSession, b: BulkRefund, actor_id: uuid.UUID) -> None:
    """Refund each order on its own (one failure doesn't stop the others) through the payment provider."""
    from core_api.modules.payments.service.order_payments import refund_in_full
    from core_api.modules.payments.service.refunds import refund_amount

    results: list[dict] = []
    why = f"incident: {b.reason}"
    for o in b.orders:
        oid = uuid.UUID(o["order_id"])
        try:
            async with db.begin_nested():
                if b.mode == "full":
                    done = await refund_in_full(db, oid, why)
                    amount = done["amount"] if done else 0
                else:
                    r = await refund_amount(db, order_id=oid, minor=int(o["amount"]), reason=why, actor_id=actor_id,
                                            note=f"bulk refund {b.id}")
                    amount = r.amount if r else 0
            results.append({"order_id": o["order_id"], "ok": amount > 0, "amount": amount,
                            **({} if amount else {"error": "Nothing left to refund"})})
        except Exception as e:  # noqa: BLE001 - recorded per order; the rest carry on
            logger.warning("bulk_refund_order_failed", bulk_refund_id=str(b.id), order_id=o["order_id"], error=str(e))
            results.append({"order_id": o["order_id"], "ok": False, "amount": 0, "error": str(e)[:200]})
    b.results = results
    b.status = "done" if all(r["ok"] for r in results) else "partly_failed"
    await record(db, actor_id=actor_id, action="bulk_refund.done", entity_type="bulk_refund", entity_id=b.id,
                 scope=b.market_city, after={"status": b.status, "refunded": sum(r["amount"] for r in results),
                                             "failed": sum(1 for r in results if not r["ok"])})
    await db.flush()


def refund_out(b: BulkRefund, orders: bool = True) -> dict:
    out = {"id": str(b.id), "market_city": b.market_city, "filters": b.filters, "mode": b.mode,
           "percent": str(b.percent) if b.percent is not None else None, "reason": b.reason, "count": b.count,
           "total": b.total, "currency": b.currency, "status": b.status, "requested_by": str(b.requested_by),
           "decided_by": str(b.decided_by) if b.decided_by else None, "decision_note": b.decision_note,
           "created_at": b.created_at.isoformat() if b.created_at else None,
           "refunded": sum(r.get("amount", 0) for r in b.results or []),
           "failed": sum(1 for r in b.results or [] if not r.get("ok"))}
    if orders:
        out["orders"], out["results"] = b.orders, b.results
    return out


# ── bulk messages ────────────────────────────────────────────────────────────

def is_test_account(email: str | None, phone: str | None) -> bool:
    """Seed and test accounts (the fixed-code domains and phone prefixes): the only people a bulk message
    reaches outside production."""
    from shared.config import get_settings

    s = get_settings().providers
    domains = [d.lower() for d in s.OTP_FIXED_CODE_EMAIL_DOMAINS]
    if email and email.rsplit("@", 1)[-1].lower() in domains:
        return True
    return bool(phone) and any(phone.startswith(p) for p in s.OTP_FIXED_CODE_PHONE_PREFIXES)  # type: ignore[union-attr]


def only_test_accounts() -> bool:
    from shared.config import get_settings

    return not get_settings().is_production


@dataclass
class Audience:
    bulk_refund_id: uuid.UUID | None = None
    city: str | None = None
    days: int = 30


async def recipients(db: AsyncSession, audience: Audience) -> tuple[str, list[dict], int]:
    """(city, [{user_id, order_id?, params}], skipped): the customers a message goes to. With a bulk
    refund, one message per refunded order (its kitchen and amount); with a city, each customer who
    ordered there in the last ``days`` once. Outside production only test accounts get it."""
    from core_api.modules.identity.models.user import User
    from core_api.modules.orders.models.order import Order
    from shared.money import format_money

    rows: list[dict] = []
    if audience.bulk_refund_id:
        b = await db.get(BulkRefund, audience.bulk_refund_id)
        if b is None:
            raise IncidentError("Bulk refund not found")
        city = b.market_city
        done = {r["order_id"]: r["amount"] for r in b.results or [] if r.get("ok")}
        for o in b.orders:
            if o["order_id"] in done:
                rows.append({"user_id": o["customer_id"], "order_id": o["order_id"],
                             "params": {"restaurant": o["restaurant"],
                                        "amount": format_money(Decimal(done[o["order_id"]]) / 100, b.currency)}})
        if not rows:
            raise IncidentError("That bulk refund hasn't refunded any order yet")
    elif audience.city:
        city = audience.city
        since = _now() - timedelta(days=max(1, min(audience.days, 90)))
        ids = (await db.execute(select(Order.customer_id).where(Order.market_city == city, Order.placed_at >= since)
                                .distinct().limit(MAX_RECIPIENTS + 1))).scalars().all()
        if len(ids) > MAX_RECIPIENTS:
            raise IncidentError(f"More than {MAX_RECIPIENTS} customers: send it in a narrower way")
        rows = [{"user_id": str(i), "order_id": None, "params": {}} for i in ids]
    else:
        raise IncidentError("Pick the customers: a bulk refund's, or a city's")
    users = {str(u.id): u for u in (await db.execute(select(User).where(User.id.in_({uuid.UUID(r["user_id"]) for r in rows}))))
             .scalars()} if rows else {}
    kept, skipped = [], 0
    for r in rows:
        u = users.get(r["user_id"])
        if u is None:
            continue
        if only_test_accounts() and not is_test_account(u.email, u.phone):
            skipped += 1
            continue
        kept.append(r)
    return city, kept, skipped


def check_template(template: str, params: dict[str, str], audience: Audience) -> dict[str, str]:
    if template not in INCIDENT_MESSAGES:
        raise IncidentError("Unknown message")
    need = incident_placeholders(template)
    if need & INCIDENT_FROM_ORDER and not audience.bulk_refund_id:
        raise IncidentError("This message names each order: send it to a bulk refund's customers")
    admin = {k: str(v).strip() for k, v in params.items() if k in INCIDENT_ADMIN_PARAMS and str(v).strip()}
    missing = sorted((need & INCIDENT_ADMIN_PARAMS) - set(admin))
    if missing:
        raise IncidentError(f"Fill in: {', '.join(missing)}")
    return admin


async def with_area(db: AsyncSession, template: str, admin: dict[str, str], city: str) -> dict[str, str]:
    """R18: {area} is the recipients' city, named as in Markets (never typed by the admin)."""
    if "area" in incident_placeholders(template):
        return {**admin, "area": await area_name(db, city)}
    return admin


def sample(template: str, language: str, params: dict[str, str]) -> dict[str, str]:
    """The message as a customer in ``language`` would read it (placeholders filled where known)."""
    title, body = INCIDENT_MESSAGES[template].get(language, INCIDENT_MESSAGES[template]["en"])
    import string

    keys = {f for _, f, _, _ in string.Formatter().parse(title + body) if f}
    values = {k: params.get(k) or "{" + k + "}" for k in keys}
    return {"title": title.format(**values), "body": body.format(**values)}


async def preview_message(db: AsyncSession, audience: Audience, template: str, params: dict[str, str]) -> dict:
    admin = check_template(template, params, audience)
    city, rows, skipped = await recipients(db, audience)
    admin = await with_area(db, template, admin, city)
    first = rows[0]["params"] if rows else {}
    return {"city": city, "recipients": len(rows), "skipped": skipped, "only_test_accounts": only_test_accounts(),
            "sample": sample(template, "en", {**first, **admin})}


async def send_message(db: AsyncSession, audience: Audience, template: str, params: dict[str, str], *, reason: str,
                       actor_id: uuid.UUID) -> BulkMessage:
    admin = check_template(template, params, audience)
    city, rows, skipped = await recipients(db, audience)
    admin = await with_area(db, template, admin, city)
    if not rows:
        raise IncidentError("Nobody to send it to" + (" (outside production only test accounts get it)" if skipped else ""))
    m = BulkMessage(scope=city, audience={"bulk_refund_id": str(audience.bulk_refund_id) if audience.bulk_refund_id else None,
                                          "city": audience.city, "days": audience.days},
                    template=template, params=admin, reason=reason, recipients=len(rows), skipped=skipped, created_by=actor_id)
    db.add(m)
    await db.flush()
    for r in rows:  # the worker sends each by push and email, in the customer's language
        await outbox.add(db, "incident.message", "bulk_message", m.id, {
            "user_id": r["user_id"], "order_id": r["order_id"], "template": template,
            "params": {**r["params"], **admin}, "bulk_message_id": str(m.id)}, "incidents")
    await record(db, actor_id=actor_id, action="customers.messaged", entity_type="bulk_message", entity_id=m.id, scope=city,
                 after={"template": template, "params": admin, "recipients": len(rows), "skipped": skipped, "reason": reason})
    return m


def message_out(m: BulkMessage) -> dict:
    return {"id": str(m.id), "scope": m.scope, "audience": m.audience, "template": m.template, "params": m.params,
            "reason": m.reason, "recipients": m.recipients, "skipped": m.skipped, "created_by": str(m.created_by),
            "created_at": m.created_at.isoformat() if m.created_at else None}
