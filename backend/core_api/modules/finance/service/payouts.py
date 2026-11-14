"""Payout runs, payee accounts and reconciliation (P13).

Weekly, finance creates a run for a country and period: every delivered order
in it becomes a line on its restaurant's and its rider's statement. A second
finance admin approves the run, and each statement is paid to the payee's
payout account (statements without an active account wait as no_account and
are paid by "retry" once the payee finishes onboarding).
"""
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit import service as audit
from core_api.modules.finance.models import PayoutAccount, PayoutRun, PayoutStatement
from core_api.modules.finance.service import statements as S
from core_api.modules.finance.service.providers import PayoutError, get_payout_provider, provider_by_name
from shared import outbox

logger = structlog.get_logger(__name__)


class FinanceError(ValueError):
    """Shown to the admin as is."""


async def _country(db: AsyncSession, code: str):  # type: ignore[no-untyped-def]
    from core_api.modules.markets.service.markets import MarketService

    c = await MarketService(db).repo.country(code)
    if c is None:
        raise FinanceError(f"Country {code} not found")
    return c


def _utc_range(start: date, end: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    return (datetime.combine(start, time(0), tzinfo=tz).astimezone(UTC),
            datetime.combine(end, time(0), tzinfo=tz).astimezone(UTC))


async def city_zones(db: AsyncSession, country: str) -> dict[str, ZoneInfo]:
    """Each city's own time zone (the country's is only a label: Boise is America/Boise)."""
    from core_api.modules.markets.models import City, Country, Region

    rows = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                             .join(Country, Country.id == City.country_id).where(Country.code == country))).all()
    return {c.code: ZoneInfo(c.timezone or r.timezone or k.timezone) for c, r, k in rows}


async def _in_period(db: AsyncSession, country: str, start: date, end: date, column):  # type: ignore[no-untyped-def]
    """``column`` falls between local midnight on ``start`` and on ``end`` in its order's own city."""
    from sqlalchemy import or_

    from core_api.modules.orders.models.order import Order

    zones = await city_zones(db, country)
    if not zones:
        return Order.id.is_(None)
    parts = []
    for code, tz in zones.items():
        a, b = _utc_range(start, end, tz)
        parts.append(and_(Order.market_city == code, column >= a, column < b))
    return or_(*parts)


async def _orders_for_period(db: AsyncSession, country: str, start: date, end: date,
                             rider_id: uuid.UUID | None = None) -> list[S.OrderForPayout]:
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import Refund
    from core_api.modules.pricing.models import OrderPricingSnapshot
    from core_api.modules.rules.models import Rule

    rows = (await db.execute(
        select(Order, OrderPricingSnapshot)
        .join(OrderPricingSnapshot, OrderPricingSnapshot.order_id == Order.id)
        .where(Order.status == "delivered", await _in_period(db, country, start, end, Order.actual_delivery_time),
               *([Order.driver_id == rider_id] if rider_id else []))
        .order_by(Order.actual_delivery_time)
    )).all()
    order_ids = [o.id for o, _ in rows]
    refunds: dict[uuid.UUID, list[dict]] = defaultdict(list)
    if order_ids:
        for r in (await db.execute(select(Refund).where(Refund.order_id.in_(order_ids), Refund.kind == "items"))).scalars():
            refunds[r.order_id] += [{**ln, "reason": r.reason, "fault": r.fault or "restaurant"}
                                    for ln in r.lines if ln.get("menu_item_id")]
    rule_ids = {uuid.UUID(v["rule_id"]) for _, snap in rows for v in snap.rule_versions
                if v["slot"] == "rider_pay:base_distance_wait"}
    rule_params = {}
    if rule_ids:
        rule_params = {str(r.id): r.params for r in (await db.execute(select(Rule).where(Rule.id.in_(rule_ids)))).scalars()}
    out = []
    for o, snap in rows:
        rider_rule = next((rule_params.get(v["rule_id"]) for v in snap.rule_versions
                           if v["slot"] == "rider_pay:base_distance_wait"), None)
        out.append(S.OrderForPayout(
            order_id=str(o.id), delivered_at=o.actual_delivery_time, restaurant_id=str(o.restaurant_id),
            rider_id=str(o.driver_id) if o.driver_id else None, lines=snap.lines, split=snap.split,
            distance=Decimal(str(snap.context.get("distance", 0))), rider_rule=rider_rule,
            started_at=o.rider_assigned_at or o.picked_up_at, refund_lines=refunds.get(o.id, []),
        ))
    return out


async def _rule(db: AsyncSession, city: str, slot: str) -> dict | None:
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    rules = await RuleService(db).resolve(Context(country=city[:2], region=city[:5], city=city))
    r = rules.get(slot)
    return r.params if r else None


async def create_run(db: AsyncSession, actor: uuid.UUID, country: str, start: date, end: date) -> PayoutRun:
    if end <= start:
        raise FinanceError("The period must end after it starts")
    c = await _country(db, country)
    overlapping = (await db.execute(select(PayoutRun).where(
        PayoutRun.country == country, PayoutRun.period_start < end, PayoutRun.period_end > start))).scalars().first()
    if overlapping:
        raise FinanceError(f"Payouts for {overlapping.period_start}–{overlapping.period_end} already cover part of this period")
    orders = await _orders_for_period(db, country, start, end)  # each city's own Monday to Monday

    run = PayoutRun(country=country, currency=c.currency, period_start=start, period_end=end, status="draft", created_by=actor)
    db.add(run)
    await db.flush()

    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.service.profile import user_profile

    by_restaurant: dict[str, list[S.OrderForPayout]] = defaultdict(list)
    by_rider: dict[str, list[S.OrderForPayout]] = defaultdict(list)
    for o in orders:
        by_restaurant[o.restaurant_id].append(o)
        if o.rider_id:
            by_rider[o.rider_id].append(o)

    totals = {"restaurants": Decimal(0), "riders": Decimal(0)}
    for rid, items in by_restaurant.items():
        r = await db.get(Restaurant, uuid.UUID(rid))
        total, summary, lines = S.restaurant_statement(items)
        db.add(PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=uuid.UUID(rid), payee_name=r.name if r else "",
                               currency=c.currency, amount=_minor(total), summary=summary, lines=lines))
        totals["restaurants"] += total
    for rider_id, items in by_rider.items():
        city = await _city_of(db, items[0].order_id)
        floor = await _rule(db, city, "rider_pay:hourly_floor") if city else None
        total, summary, lines = S.rider_statement(items, Decimal(str(floor["per_active_hour"])) if floor else None)
        profile = await user_profile(db, uuid.UUID(rider_id)) or {}
        db.add(PayoutStatement(run_id=run.id, payee_type="rider", payee_id=uuid.UUID(rider_id), payee_name=profile.get("name", ""),
                               currency=c.currency, amount=_minor(total), summary=summary, lines=lines))
        totals["riders"] += total
    run.totals = {"orders": len(orders), "restaurants": str(S.m(totals["restaurants"])), "riders": str(S.m(totals["riders"])),
                  "restaurant_statements": len(by_restaurant), "rider_statements": len(by_rider)}
    await db.flush()
    await audit.record(db, actor_id=actor, action="payout_run.created", entity_type="payout_run", entity_id=run.id,
                       scope=country, after={"period": f"{start}..{end}", **run.totals})
    return run


async def preview_restaurant(db: AsyncSession, country: str, start: date, end: date, restaurant_id: uuid.UUID) -> dict:
    """A restaurant's statement for a period as a payout run would make it, without making
    one (runs can't overlap; this shows what the next run will pay, e.g. mid-week)."""
    if end <= start:
        raise FinanceError("The period must end after it starts")
    orders = [o for o in await _orders_for_period(db, country, start, end) if o.restaurant_id == str(restaurant_id)]
    total, summary, lines = S.restaurant_statement(orders)
    return {"restaurant_id": str(restaurant_id), "period": {"start": start.isoformat(), "end": end.isoformat()},
            "total": str(total), "summary": summary, "lines": lines}


async def _city_of(db: AsyncSession, order_id: str) -> str | None:
    from core_api.modules.orders.service.lookup import order_market

    return await order_market(db, uuid.UUID(order_id)) or None


def _minor(v: Decimal) -> int:
    return int((v * 100).to_integral_value())


async def approve_and_pay(db: AsyncSession, actor: uuid.UUID, run_id: uuid.UUID) -> PayoutRun:
    run = await db.get(PayoutRun, run_id, with_for_update=True)
    if run is None:
        raise FinanceError("Payout run not found")
    if run.status != "draft":
        raise FinanceError(f"This run is already {run.status}")
    if run.created_by == actor:
        raise FinanceError("A second finance admin must approve the payouts you prepared")
    run.status, run.approved_by, run.approved_at = "approved", actor, datetime.now(UTC)
    await audit.record(db, actor_id=actor, action="payout_run.approved", entity_type="payout_run", entity_id=run.id,
                       scope=run.country, after=run.totals)
    await pay_pending(db, run)
    return run


async def pay_pending(db: AsyncSession, run: PayoutRun) -> None:
    """Pay every statement not yet paid; payees without an active account wait."""
    stmts = (await db.execute(select(PayoutStatement).where(
        PayoutStatement.run_id == run.id, PayoutStatement.status.in_(("pending", "failed", "no_account"))))).scalars().all()
    for st in stmts:
        if st.amount <= 0:
            st.status = "paid"  # nothing to send
            continue
        acct = (await db.execute(select(PayoutAccount).where(
            PayoutAccount.payee_type == st.payee_type, PayoutAccount.payee_id == st.payee_id,
            PayoutAccount.country == run.country, PayoutAccount.status == "active"))).scalars().first()
        if acct is None:
            st.status, st.error = "no_account", "The payee hasn't set up a payout account"
            continue
        try:
            st.transfer_id = await provider_by_name(acct.provider).transfer(acct.external_id, st.amount, st.currency, f"{run.id}:{st.id}")
            st.status, st.error = "paid", None
            await outbox.add(db, "payout.paid", st.payee_type, st.payee_id, {
                "statement_id": str(st.id), "run_id": str(run.id), "amount": st.amount, "currency": st.currency,
                "payee_type": st.payee_type, "payee_id": str(st.payee_id), "user_id": None}, "finance")
        except PayoutError as e:
            st.status, st.error = "failed", str(e)[:500]
            logger.error("payout_failed", statement_id=str(st.id), error=str(e))
    await db.flush()
    statuses = {s for (s,) in (await db.execute(select(PayoutStatement.status).where(PayoutStatement.run_id == run.id))).all()}
    run.status = "paid" if statuses <= {"paid"} else "partially_paid"
    if run.status == "paid":
        run.paid_at = datetime.now(UTC)
    await db.flush()


async def retry(db: AsyncSession, actor: uuid.UUID, run_id: uuid.UUID) -> PayoutRun:
    run = await db.get(PayoutRun, run_id, with_for_update=True)
    if run is None:
        raise FinanceError("Payout run not found")
    if run.status not in ("approved", "partially_paid"):
        raise FinanceError("Only an approved run with unpaid statements can be retried")
    await pay_pending(db, run)
    await audit.record(db, actor_id=actor, action="payout_run.retried", entity_type="payout_run", entity_id=run.id,
                       scope=run.country, after={"status": run.status})
    return run


# ── a rider's week so far (P18) ───────────────────────────────────────────────

async def rider_week(db: AsyncSession, rider_id: uuid.UUID, country: str, now: datetime | None = None) -> dict:
    """This week (Monday to now, local time) as the weekly run will pay it: per
    day, today's deliveries, and the hourly-floor top-up so far. Paid the
    Monday after the week ends."""
    from datetime import timedelta

    from core_api.modules.orders.models.order import Order

    c = await _country(db, country)
    # "This week" is in the rider's city (their latest order; a new rider: the country's live city).
    city = (await db.execute(select(Order.market_city).where(Order.driver_id == rider_id, Order.market_city.is_not(None))
                             .order_by(Order.created_at.desc()).limit(1))).scalar()
    if city is None:
        from core_api.modules.markets.models import City

        city = (await db.execute(select(City.code).where(City.code.like(f"{country}-%"), City.status.in_(("live", "beta")))
                                 .order_by(City.code).limit(1))).scalar()
    tz = (await city_zones(db, country)).get(city or "", ZoneInfo(c.timezone))
    local_now = (now or datetime.now(UTC)).astimezone(tz)
    today = local_now.date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=7)
    orders = await _orders_for_period(db, country, start, end, rider_id)
    floor = await _rule(db, city, "rider_pay:hourly_floor") if city else None
    floor_rate = Decimal(str(floor["per_active_hour"])) if floor else None
    total, summary, lines = S.rider_statement(orders, floor_rate)
    if lines:  # "Boise Bowl Co. → Hyde Park" on each line
        from core_api.modules.orders.api.v1.internal import drop_area

        found = {str(o.id): o for o in (await db.execute(select(Order).where(
            Order.id.in_([uuid.UUID(ln["order_id"]) for ln in lines])))).scalars()}
        for ln in lines:
            o = found.get(ln["order_id"])
            ln["restaurant_name"] = o.restaurant_name if o else ""
            ln["drop_area"] = drop_area(o.delivery_address) if o else None
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        day_lines = [ln for ln in lines if datetime.fromisoformat(ln["delivered_at"]).astimezone(tz).date() == d]
        days.append({"date": d.isoformat(), "deliveries": len(day_lines),
                     "total": str(S.m(sum((Decimal(ln["total"]) for ln in day_lines), Decimal(0))))})
    today_lines = [ln for ln in lines if datetime.fromisoformat(ln["delivered_at"]).astimezone(tz).date() == today]
    return {"currency": c.currency, "city": city, "period_start": start.isoformat(), "period_end": end.isoformat(),
            "payout_date": end.isoformat(), "total": str(total), "summary": summary, "days": days,
            "today": {"date": today.isoformat(), "total": str(S.m(sum((Decimal(ln["total"]) for ln in today_lines), Decimal(0)))),
                      "lines": today_lines}}


# ── payee accounts ────────────────────────────────────────────────────────────

async def open_account(db: AsyncSession, payee_type: str, payee_id: uuid.UUID, country: str, profile: dict,
                       return_url: str) -> tuple[PayoutAccount, str | None]:
    provider = get_payout_provider(country)
    existing = (await db.execute(select(PayoutAccount).where(and_(
        PayoutAccount.payee_type == payee_type, PayoutAccount.payee_id == payee_id,
        PayoutAccount.provider == provider.name)))).scalars().first()
    if existing:
        return existing, None
    created = await provider.create_account({**profile, "type": payee_type, "id": str(payee_id), "country": country,
                                             "return_url": return_url})
    acct = PayoutAccount(payee_type=payee_type, payee_id=payee_id, provider=provider.name, external_id=created["external_id"],
                         status=created["status"], country=country)
    db.add(acct)
    await db.flush()
    return acct, created.get("onboarding_url")


async def mark_account(db: AsyncSession, external_id: str, active: bool) -> PayoutAccount | None:
    acct = (await db.execute(select(PayoutAccount).where(PayoutAccount.external_id == external_id))).scalars().first()
    if acct is not None:
        acct.status = "active" if active else "restricted"
        await db.flush()
    return acct


# ── reconciliation ────────────────────────────────────────────────────────────

async def reconciliation(db: AsyncSession, country: str, start: date, end: date) -> dict:
    """Money in vs money owed for a period: orders, captured payments, refunds,
    tax, payouts, platform revenue; and anything that doesn't line up."""
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import PaymentIntent, Refund
    from core_api.modules.pricing.models import OrderPricingSnapshot

    c = await _country(db, country)
    orders = (await db.execute(select(Order).where(
        await _in_period(db, country, start, end, Order.created_at)))).scalars().all()
    ids = [o.id for o in orders]
    intents = (await db.execute(select(PaymentIntent).where(PaymentIntent.order_id.in_(ids)))).scalars().all() if ids else []
    refunds = (await db.execute(select(Refund).where(Refund.order_id.in_(ids)))).scalars().all() if ids else []
    snaps = {s.order_id: s for s in (await db.execute(select(OrderPricingSnapshot).where(
        OrderPricingSnapshot.order_id.in_(ids)))).scalars()} if ids else {}

    captured = [i for i in intents if i.status in ("succeeded", "partially_refunded", "refunded")]
    by_order: dict[uuid.UUID, int] = defaultdict(int)
    by_provider: dict[str, dict[str, int]] = defaultdict(lambda: {"captured": 0, "refunded": 0})
    for i in captured:
        by_order[i.order_id] += i.amount
        by_provider[i.provider]["captured"] += i.amount
        by_provider[i.provider]["refunded"] += i.refunded_amount or 0
    refunded_by_order: dict[uuid.UUID, int] = defaultdict(int)
    for r in refunds:
        refunded_by_order[r.order_id] += r.amount

    issues = []
    delivered = [o for o in orders if o.status == "delivered"]
    for o in orders:
        paid = by_order.get(o.id, 0)
        total_minor = int(Decimal(o.total) * 100)
        if o.status in ("placed", "accepted", "preparing", "almost_ready", "ready", "picked_up", "delivered") and paid < total_minor:
            issues.append({"order_id": str(o.id), "issue": "paid_less_than_total", "status": o.status, "total": total_minor, "captured": paid})
        if o.status == "cancelled" and paid and refunded_by_order.get(o.id, 0) < paid:
            issues.append({"order_id": str(o.id), "issue": "cancelled_not_refunded", "captured": paid,
                           "refunded": refunded_by_order.get(o.id, 0)})
        snap = snaps.get(o.id)
        if snap is not None and Decimal(snap.total) != Decimal(o.total):
            issues.append({"order_id": str(o.id), "issue": "snapshot_total_mismatch"})
    pending_refunds = sum(1 for r in refunds if r.status not in ("succeeded", "processed"))

    def split_sum(key: str) -> Decimal:
        return S.m(sum((Decimal(str(snaps[o.id].split.get(key, 0))) for o in delivered if o.id in snaps), Decimal(0)))

    captured_total = sum(by_order.values())
    refunded_total = sum(refunded_by_order.values())
    return {
        "country": country, "currency": c.currency, "period": {"start": start.isoformat(), "end": end.isoformat()},
        "orders": {"total": len(orders), "delivered": len(delivered), "cancelled": sum(1 for o in orders if o.status == "cancelled"),
                   "open": sum(1 for o in orders if o.status not in ("delivered", "cancelled"))},
        "money": {"captured": captured_total, "refunded": refunded_total, "net_collected": captured_total - refunded_total,
                  "delivered_gmv": S._minor_str(sum((Decimal(o.total) for o in delivered), Decimal(0))),
                  "tax_owed": S._minor_str(split_sum("tax")), "restaurant_payable": S._minor_str(split_sum("restaurant")),
                  "rider_payable": S._minor_str(split_sum("rider")), "platform_revenue": S._minor_str(split_sum("platform")),
                  # Item 1: what the payment providers keep, and the platform after them (orders priced
                  # before fees were recorded count as 0 here; the contribution report estimates them).
                  "payment_fees": S._minor_str(split_sum("payment_fees")),
                  "platform_after_payment_fees": S._minor_str(split_sum("platform") - split_sum("payment_fees"))},
        "by_provider": by_provider, "refunds_not_settled": pending_refunds,
        "issues": issues,
    }
