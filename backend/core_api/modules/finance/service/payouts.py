"""Payout runs, payee accounts and reconciliation (P13).

Weekly, finance creates a run for a country and period: every delivered order
in it becomes a line on its restaurant's and its rider's statement. A second
finance admin approves the run, and each statement is paid to the payee's
payout account (statements wait as no_account, or onboarding while the payee
finishes set-up, and are paid as soon as the account is ready: service/connect.py).

The provider (Stripe Connect, Razorpay Route, the fake) is the country's choice in
Markets (countries.payout_provider; providers.py): accounts are opened with it,
and a run pays each payee's account with that provider.
"""
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit import service as audit
from core_api.modules.finance.models import PayoutAccount, PayoutRun, PayoutRunOrder, PayoutStatement
from core_api.modules.finance.service import statements as S
from core_api.modules.finance.service.providers import (
    NoPayoutProvider,
    PayoutError,
    PayoutProvider,
    country_payout_provider,
)
from shared import outbox
from shared.config import get_settings

logger = structlog.get_logger(__name__)


class FinanceError(ValueError):
    """Shown to the admin as is."""


async def _provider(db: AsyncSession, country: str) -> PayoutProvider:
    """The country's payout provider from Markets; none set -> FinanceError (shown to the admin)."""
    try:
        return await country_payout_provider(db, country)
    except NoPayoutProvider as e:
        raise FinanceError(str(e)) from e


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
    """Each city's own time zone (Boise is America/Boise): days shown on a payee's screen."""
    from core_api.modules.markets.models import City, Country, Region

    rows = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                             .join(Country, Country.id == City.country_id).where(Country.code == country))).all()
    return {c.code: ZoneInfo(c.timezone or r.timezone or k.timezone) for c, r, k in rows}


def payout_tz(c) -> ZoneInfo:  # type: ignore[no-untyped-def]
    """R27: the zone a country's payout weeks are counted in (Markets payout_timezone, else its timezone).
    One zone per country, so a week starts at the same instant for every kitchen and rider in it."""
    from core_api.modules.markets.models import payout_zone

    return ZoneInfo(payout_zone(c))


def week_window(start: date, end: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """A payout period as UTC instants: local midnight on ``start`` to local midnight on ``end``
    (``end`` not included) in the payout zone. Across a DST change the week is 167 or 169 hours."""
    return _utc_range(start, end, tz)


async def _in_period(db: AsyncSession, country: str, start: date, end: date, column):  # type: ignore[no-untyped-def]
    """``column`` falls in the week: midnight on ``start`` to midnight on ``end`` in the country's payout zone
    (R27; before, each order's own city zone), for orders in the country's cities."""
    from core_api.modules.markets.models import City, Country
    from core_api.modules.orders.models.order import Order

    c = await _country(db, country)
    codes = select(City.code).join(Country, Country.id == City.country_id).where(Country.code == country)
    a, b = week_window(start, end, payout_tz(c))
    return and_(Order.market_city.in_(codes), column >= a, column < b)


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
    # R20: app store review orders cost nothing and pay nobody (their kitchen and delivery
    # partner are review accounts): never on a statement.
    rows = [(o, snap) for o, snap in rows if not (snap.context or {}).get("review")]
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
            batch_position=o.batch_position, batch_bonus=o.batch_bonus, card_fee=o.card_fee,
        ))
    return out


async def _rule(db: AsyncSession, city: str, slot: str) -> dict | None:
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    rules = await RuleService(db).resolve(Context(country=city[:2], region=city[:5], city=city))
    r = rules.get(slot)
    return r.params if r else None


DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def local_today(tz: ZoneInfo, now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(tz).date()


def check_week(start: date, end: date, today: date) -> None:
    """A run pays one week that has ended (R12): Monday to Sunday in the country's time zone,
    sent as Monday to the next Monday (end not included). No unfinished week: its orders
    could still change."""
    if start.weekday() != 0 or end != start + timedelta(days=7):
        raise FinanceError("A payout run covers one week, Monday to Sunday")
    if end > today:
        raise FinanceError(f"The week {start.isoformat()} to {(end - timedelta(days=1)).isoformat()} hasn't ended yet; "
                           f"prepare it from Monday {end.isoformat()}")


def week_of(at: datetime, tz: ZoneInfo) -> tuple[date, date]:
    """R41: the payout week an instant belongs to: Monday 00:00 to the next Monday 00:00 in the payout zone (so
    Sunday 23:59:59 is still that week, Monday 00:00 is the next). Weeks never overlap and leave no gap."""
    local = at.astimezone(tz).date()
    monday = local - timedelta(days=local.weekday())
    return monday, monday + timedelta(days=7)


def ended_weeks(today: date, n: int = 8) -> list[tuple[date, date]]:
    """The last ``n`` weeks that have ended by ``today`` (a local date), newest first."""
    this_monday = today - timedelta(days=today.weekday())
    return [(this_monday - timedelta(days=7 * i), this_monday - timedelta(days=7 * (i - 1))) for i in range(1, n + 1)]


async def payout_weekday(db: AsyncSession, country: str) -> int:
    """The country's payout day (business rule payout_schedule; Monday by default), 0 = Monday."""
    sched = await _rule(db, country, "commission:payout_schedule") or {}
    day = sched.get("day", "mon")
    return DAYS.index(day) if day in DAYS else 0


async def next_payout_day(db: AsyncSession, country: str, now: datetime | None = None) -> date:
    """The date unpaid (reversed or failed) statements are paid again: the country's next
    payout day, today if today is one (the scheduler retries them hourly on that day)."""
    c = await _country(db, country)
    today = local_today(payout_tz(c), now)
    return today + timedelta(days=(await payout_weekday(db, country) - today.weekday()) % 7)


@dataclass
class WeekStatements:
    """A period's statements exactly as a payout run makes them (R14: the one source for the run,
    reconciliation and the contribution report). Amounts in major units."""
    orders: list[S.OrderForPayout]
    restaurants: list[tuple[str, Decimal, dict, list[dict]]]       # (restaurant id, total, summary, lines)
    riders: list[tuple[str, Decimal, dict, list[dict], list[str]]]  # (rider id, total, summary, lines, order ids)

    @property
    def restaurants_total(self) -> Decimal:
        return S.m(sum((t for _, t, _, _ in self.restaurants), Decimal(0)))

    @property
    def riders_total(self) -> Decimal:
        return S.m(sum((t for _, t, _, _, _ in self.riders), Decimal(0)))

    def kitchen_sum(self, key: str) -> Decimal:
        """A kitchen statement total across the week (commission_tax, tds, commission ...)."""
        return S.m(sum((S.D(s.get(key)) for _, _, s, _ in self.restaurants), Decimal(0)))

    @property
    def top_ups(self) -> Decimal:
        """Minimum pay top-ups: what the platform adds so active hours earn the city's minimum."""
        return S.m(sum((S.D(s.get("floor_top_up")) for _, _, s, _, _ in self.riders), Decimal(0)))

    def top_up_per_order(self) -> dict[str, Decimal]:
        """Each delivery partner's top-up shared evenly across their orders (for per-order and per-city views)."""
        out: dict[str, Decimal] = {}
        for _, _, s, _, ids in self.riders:
            if ids:
                for oid in ids:
                    out[oid] = S.D(s.get("floor_top_up")) / len(ids)
        return out


async def kitchen_tax_rates(db: AsyncSession, scope: str) -> tuple[Decimal, Decimal]:
    """(commission tax %, TDS %) for a kitchen's city or country (R16 business rules; none set: 0)."""
    ct = await _rule(db, scope, "business:commission_tax")
    tds = await _rule(db, scope, "business:payout_tds")
    return Decimal(str((ct or {}).get("rate_percent", 0))), Decimal(str((tds or {}).get("rate_percent", 0)))


async def week_statements(db: AsyncSession, country: str, start: date, end: date) -> WeekStatements:
    orders = await _orders_for_period(db, country, start, end)  # each city's own Monday to Monday
    by_restaurant: dict[str, list[S.OrderForPayout]] = defaultdict(list)
    by_rider: dict[str, list[S.OrderForPayout]] = defaultdict(list)
    for o in orders:
        by_restaurant[o.restaurant_id].append(o)
        if o.rider_id:
            by_rider[o.rider_id].append(o)
    restaurants = []
    for rid, items in by_restaurant.items():
        pct = await kitchen_tax_rates(db, await _city_of(db, items[0].order_id) or country)
        restaurants.append((rid, *S.restaurant_statement(items, *pct)))
    riders = []
    for rider_id, items in by_rider.items():
        city = await _city_of(db, items[0].order_id)
        floor = await _rule(db, city, "rider_pay:hourly_floor") if city else None
        total, summary, lines = S.rider_statement(items, Decimal(str(floor["per_active_hour"])) if floor else None)
        riders.append((rider_id, total, summary, lines, [i.order_id for i in items]))
    return WeekStatements(orders, restaurants, riders)


async def open_carries(db: AsyncSession, country: str, before: date, lock: bool = False) -> dict[str, S.Carry]:
    """R23: each kitchen's balance still below zero from runs that ended by ``before``: its
    statements whose amount is below zero and that no later statement has carried yet. Usually
    one per kitchen (its latest week); several when runs were prepared out of order.
    ``lock``: hold them (FOR UPDATE) until the run that carries them commits, so two runs never
    carry the same balance."""
    q = (select(PayoutStatement, PayoutRun.period_start).join(PayoutRun, PayoutRun.id == PayoutStatement.run_id)
         .where(PayoutRun.country == country, PayoutRun.period_end <= before, PayoutStatement.payee_type == "restaurant",
                PayoutStatement.amount < 0, PayoutStatement.carried_to.is_(None))
         .order_by(PayoutRun.period_start))
    if lock:
        q = q.with_for_update(of=PayoutStatement)
    found: dict[str, list[S.Carry]] = defaultdict(list)
    for st, started in (await db.execute(q)).all():
        found[str(st.payee_id)].append(S.Carry(amount=st.amount, weeks=max(st.negative_weeks, 1),
                                               since=st.negative_since or started, statements=(str(st.id),)))
    return {rid: c for rid, cs in found.items() if (c := S.combine(cs)) is not None}


def kitchen_balances(week: WeekStatements, carries: dict[str, S.Carry], start: date,
                     disputes: dict[str, int] | None = None) -> dict[str, S.Balance]:
    """R23: every kitchen on the run, with what it carries in: the week's kitchens and any
    kitchen with a balance below zero and no orders this week (a statement with only the carry).
    R39: ``disputes``: each kitchen's chargeback holds, releases and losses (minor units), in its net."""
    disputes = disputes or {}
    nets = {rid: _minor(total) for rid, total, _, _ in week.restaurants}
    for rid, amount in disputes.items():
        nets[rid] = nets.get(rid, 0) + amount
    return {rid: S.balance(nets.get(rid, 0), carries.get(rid), start) for rid in [*nets, *(r for r in carries if r not in nets)]}


def carry_totals(balances: list[S.Balance]) -> dict[str, int]:
    """Minor units: carried in from last week (<= 0), carried to next week (<= 0), paid this week."""
    return {"carried_in": sum(b.carried_in for b in balances), "carried_forward": sum(b.carried_forward for b in balances),
            "to_pay": sum(b.to_pay for b in balances)}


async def create_run(db: AsyncSession, actor: uuid.UUID, country: str, start: date, end: date,
                     now: datetime | None = None) -> PayoutRun:
    if end <= start:
        raise FinanceError("The period must end after it starts")
    c = await _country(db, country)
    check_week(start, end, local_today(payout_tz(c), now))
    overlapping = (await db.execute(select(PayoutRun).where(
        PayoutRun.country == country, PayoutRun.period_start < end, PayoutRun.period_end > start))).scalars().first()
    if overlapping:
        raise FinanceError(f"Payouts for {overlapping.period_start}–{overlapping.period_end} already cover part of this period")
    week = await week_statements(db, country, start, end)
    carries = await open_carries(db, country, start, lock=True)
    from core_api.modules.payments.service import disputes as DS

    held = await DS.payout_adjustments(db, country, lock=True)  # R39: chargebacks
    balances = kitchen_balances(week, carries, start, {rid: sum(a.amount for a in adj) for rid, adj in held.items()})

    run = PayoutRun(country=country, currency=c.currency, period_start=start, period_end=end, status="draft", created_by=actor)
    db.add(run)
    await db.flush()

    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.service.profile import user_profile

    own = {rid: (summary, lines) for rid, _, summary, lines in week.restaurants}
    carried: list[tuple[PayoutStatement, S.Carry]] = []
    for rid, bal in balances.items():
        r = await db.get(Restaurant, uuid.UUID(rid))
        summary, lines = own.get(rid) or S.restaurant_statement([])[1:]
        if bal.carried_in:  # R23: "Carried from last week", netted into this week's amount
            summary = {**summary, "carried_from_last_week": S.major(bal.carried_in), "amount": S.major(bal.amount)}
        if rid in held:  # R39: chargeback holds (-), releases (+) and losses (-), netted into the amount
            summary = {**summary, "disputes": S.major(sum(a.amount for a in held[rid])),
                       "dispute_lines": DS.summary_lines(held[rid]), "amount": S.major(bal.amount)}
        st = PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=uuid.UUID(rid), payee_name=r.name if r else "",
                             currency=c.currency, amount=bal.amount, summary=summary, lines=lines, carried_in=bal.carried_in,
                             negative_weeks=bal.negative_weeks, negative_since=bal.negative_since)
        db.add(st)
        if rid in carries:
            carried.append((st, carries[rid]))
        if rid in held:
            await db.flush()
            DS.mark_applied(held[rid], st.id)
    for rider_id, total, summary, lines, _ in week.riders:
        profile = await user_profile(db, uuid.UUID(rider_id)) or {}
        db.add(PayoutStatement(run_id=run.id, payee_type="rider", payee_id=uuid.UUID(rider_id), payee_name=profile.get("name", ""),
                               currency=c.currency, amount=_minor(total), summary=summary, lines=lines))
    await db.flush()
    await _claim_orders(db, run, [o.order_id for o in week.orders])
    for st, carry in carried:  # each balance is carried once: the update only takes statements no run has carried
        done = await db.execute(update(PayoutStatement).where(
            PayoutStatement.id.in_([uuid.UUID(i) for i in carry.statements]), PayoutStatement.carried_to.is_(None))
            .values(carried_to=st.id).execution_options(synchronize_session=False))
        if done.rowcount != len(carry.statements):  # type: ignore[attr-defined]
            raise FinanceError("Another payout run carried this restaurant's balance at the same time: try again")
    ct = carry_totals(list(balances.values()))
    run.totals = {"orders": len(week.orders), "restaurants": str(week.restaurants_total), "riders": str(week.riders_total),
                  "min_pay_top_ups": str(week.top_ups),
                  "commission_tax": str(week.kitchen_sum("commission_tax")), "tds": str(week.kitchen_sum("tds")),
                  "restaurant_statements": len(balances), "rider_statements": len(week.riders),
                  # R23: kitchens' balances below zero, in and out, and what the run pays kitchens after them
                  "kitchen_carried_in": S.major(ct["carried_in"]), "kitchen_carried_forward": S.major(ct["carried_forward"]),
                  "restaurants_to_pay": S.major(ct["to_pay"]),
                  "kitchens_to_collect": sum(1 for b in balances.values() if S.to_collect(b.negative_weeks))}
    await db.flush()
    await audit.record(db, actor_id=actor, action="payout_run.created", entity_type="payout_run", entity_id=run.id,
                       scope=country, after={"period": f"{start}..{end}", **run.totals})
    return run


async def _claim_orders(db: AsyncSession, run: PayoutRun, order_ids: list[str]) -> None:
    """R41: an order is paid by one payout run only. payout_run_orders has the order as its primary key; runs
    prepared before it (no rows there) are checked through their statement lines."""
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy.exc import IntegrityError

    if not order_ids:
        return
    legacy = (await db.execute(text(
        "SELECT line->>'order_id', s.run_id FROM payout_statements s, jsonb_array_elements(s.lines) AS line "
        "WHERE s.run_id <> :run AND s.payee_type = 'restaurant' AND line->>'order_id' = ANY(:ids) LIMIT 1"),
        {"run": run.id, "ids": order_ids})).first()
    if legacy:
        raise FinanceError(f"Order {legacy[0][:8].upper()} is already on payout run {str(legacy[1])[:8]}: an order is paid once")
    try:
        async with db.begin_nested():
            await db.execute(insert(PayoutRunOrder), [{"order_id": uuid.UUID(o), "run_id": run.id} for o in order_ids])
    except IntegrityError as e:
        raise FinanceError("An order of this week is already on another payout run: an order is paid once") from e


async def preview_restaurant(db: AsyncSession, country: str, start: date, end: date, restaurant_id: uuid.UUID) -> dict:
    """A restaurant's statement for a period as a payout run would make it, without making
    one (runs can't overlap; this shows what the next run will pay, e.g. mid-week)."""
    if end <= start:
        raise FinanceError("The period must end after it starts")
    orders = [o for o in await _orders_for_period(db, country, start, end) if o.restaurant_id == str(restaurant_id)]
    pct = await kitchen_tax_rates(db, (await _city_of(db, orders[0].order_id) if orders else None) or country)
    total, summary, lines = S.restaurant_statement(orders, *pct)
    bal = S.balance(_minor(total), (await open_carries(db, country, start)).get(str(restaurant_id)), start)
    return {"restaurant_id": str(restaurant_id), "period": {"start": start.isoformat(), "end": end.isoformat()},
            "total": str(total), "summary": summary, "lines": lines,
            # R23: what earlier weeks left below zero, and what a run would pay after it (minor units)
            "carried_in": bal.carried_in, "amount": bal.amount}


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
    provider = await _provider(db, run.country)
    if get_settings().APP_ENV == "qa":
        # R14: QA (demo data, real test-mode payouts) approves a run only when every payee who is
        # owed money has a ready payout account; otherwise nothing is approved or sent.
        waiting = await _payees_not_ready(db, run, provider)
        if waiting:
            raise FinanceError(f"On QA a run is approved only when every payee's payout account is ready: {waiting} "
                               "aren't yet. Send them a set-up link from Statements first.")
    run.status, run.approved_by, run.approved_at = "approved", actor, datetime.now(UTC)
    await audit.record(db, actor_id=actor, action="payout_run.approved", entity_type="payout_run", entity_id=run.id,
                       scope=run.country, after=run.totals)
    await pay_pending(db, run, provider)
    return run


async def _payees_not_ready(db: AsyncSession, run: PayoutRun, provider: PayoutProvider) -> int:
    """How many of the run's payees with money owed have no active payout account with the provider."""
    owed = (await db.execute(select(PayoutStatement).where(PayoutStatement.run_id == run.id, PayoutStatement.amount > 0))).scalars().all()
    if not owed:
        return 0
    ready = {(a.payee_type, a.payee_id) for a in (await db.execute(select(PayoutAccount).where(
        PayoutAccount.country == run.country, PayoutAccount.provider == provider.name, PayoutAccount.status == "active",
        PayoutAccount.payee_id.in_([s.payee_id for s in owed])))).scalars()}
    return sum(1 for s in owed if (s.payee_type, s.payee_id) not in ready)


async def pay_pending(db: AsyncSession, run: PayoutRun, provider: PayoutProvider,
                      payee: tuple[str, uuid.UUID] | None = None) -> None:
    """Pay every statement not yet paid with the country's provider (or just ``payee``'s).
    Only accounts with payouts enabled are paid; the others wait: ``no_account`` (never
    set up) or ``onboarding`` (set-up not finished), and are paid when the account is
    ready (connect.pay_waiting) or on retry. The idempotency key is the statement and its
    attempt: a transfer that timed out is retried with the same key (never paid twice),
    one the provider refused or that was reversed gets a new one."""
    q = select(PayoutStatement).where(PayoutStatement.run_id == run.id,
                                      PayoutStatement.status.in_(("pending", "failed", "no_account", "onboarding", "reversed")))
    if payee:
        q = q.where(PayoutStatement.payee_type == payee[0], PayoutStatement.payee_id == payee[1])
    for st in (await db.execute(q)).scalars().all():
        settled = S.settle(st.amount)
        if settled:  # nothing to send: zero is paid; below zero is carried to the next statement (R23), never charged
            st.status, st.error = settled, None
            continue
        accts = (await db.execute(select(PayoutAccount).where(
            PayoutAccount.payee_type == st.payee_type, PayoutAccount.payee_id == st.payee_id,
            PayoutAccount.country == run.country, PayoutAccount.provider == provider.name))).scalars().all()
        acct = next((a for a in accts if a.status == "active"), None)
        if acct is None:
            if accts:
                st.status, st.error = "onboarding", "Waiting for the payee to finish setting up payouts"
            else:
                st.status, st.error = "no_account", "The payee hasn't set up a payout account"
            continue
        try:
            st.transfer_id = await provider.transfer(acct.external_id, st.amount, st.currency, f"{run.id}:{st.id}:{st.attempts}")
            st.status, st.error, st.transferred_at = "paid", None, datetime.now(UTC)
            await outbox.add(db, "payout.paid", st.payee_type, st.payee_id, {
                "statement_id": str(st.id), "run_id": str(run.id), "amount": st.amount, "currency": st.currency,
                "payee_type": st.payee_type, "payee_id": str(st.payee_id), "user_id": None}, "finance")
        except PayoutError as e:
            st.status, st.error = "failed", str(e)[:500]
            if e.final:
                st.attempts += 1  # refused: the next try is a new request
            logger.error("payout_failed", statement_id=str(st.id), error=str(e), final=e.final)
    await db.flush()
    statuses = {s for (s,) in (await db.execute(select(PayoutStatement.status).where(PayoutStatement.run_id == run.id))).all()}
    run.status = "paid" if statuses <= {"paid", "carried"} else "partially_paid"
    if run.status == "paid":
        run.paid_at = datetime.now(UTC)
    await db.flush()


async def retry(db: AsyncSession, actor: uuid.UUID, run_id: uuid.UUID) -> PayoutRun:
    run = await db.get(PayoutRun, run_id, with_for_update=True)
    if run is None:
        raise FinanceError("Payout run not found")
    if run.status not in ("approved", "partially_paid"):
        raise FinanceError("Only an approved run with unpaid statements can be retried")
    await pay_pending(db, run, await _provider(db, run.country))
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
    tz = (await city_zones(db, country)).get(city or "", ZoneInfo(c.timezone))  # days and times on the city's clock
    # R27: the week itself is the payout run's (the country's payout zone), so this adds up to the statement.
    pay_today = (now or datetime.now(UTC)).astimezone(payout_tz(c)).date()
    today = (now or datetime.now(UTC)).astimezone(tz).date()
    start = pay_today - timedelta(days=pay_today.weekday())
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
    return {"currency": c.currency, "city": city, "time_zone": tz.key, "period_start": start.isoformat(), "period_end": end.isoformat(),
            "payout_date": end.isoformat(), "total": str(total), "summary": summary, "days": days,
            "today": {"date": today.isoformat(), "total": str(S.m(sum((Decimal(ln["total"]) for ln in today_lines), Decimal(0)))),
                      "lines": today_lines}}


# ── payee accounts ────────────────────────────────────────────────────────────

async def _open_key(db: AsyncSession, payee_type: str, payee_id: uuid.UUID) -> str:
    """The idempotency key for opening this payee's provider account: the same for a retried or
    double-tapped request, new when the payee opens again later (their earlier accounts counted)
    and in a reseeded environment, where ids repeat but the payee is a new row (its creation time).
    Stripe keeps a key for 24 hours and refuses it with different parameters."""
    from sqlalchemy import func

    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.models.user import User

    model = Restaurant if payee_type == "restaurant" else User
    since = (await db.execute(select(model.created_at).where(model.id == payee_id))).scalar_one_or_none()
    before = (await db.execute(select(func.count()).select_from(PayoutAccount).where(
        PayoutAccount.payee_type == payee_type, PayoutAccount.payee_id == payee_id))).scalar_one()
    return f"{payee_type}-{payee_id}-{int(since.timestamp()) if since else 0}-{before}"


async def open_account(db: AsyncSession, payee_type: str, payee_id: uuid.UUID, country: str, profile: dict,
                       return_url: str | None = None) -> tuple[PayoutAccount, str | None]:
    """Create the payee's account with the country's provider, or reuse it; with
    hosted onboarding (Stripe), a fresh link to finish set-up (None once ready)."""
    from core_api.modules.finance.service import connect

    provider = await _provider(db, country)
    acct = (await db.execute(select(PayoutAccount).where(and_(
        PayoutAccount.payee_type == payee_type, PayoutAccount.payee_id == payee_id,
        PayoutAccount.provider == provider.name)))).scalars().first()
    if acct is None:
        created = await provider.create_account({**profile, "type": payee_type, "id": str(payee_id), "country": country,
                                                 "return_url": return_url,
                                                 "open_key": await _open_key(db, payee_type, payee_id)})
        acct = PayoutAccount(payee_type=payee_type, payee_id=payee_id, provider=provider.name, external_id=created["external_id"],
                             status=created["status"], country=country, requirements_due=[])
        connect.mark_created(acct)
        db.add(acct)
        await db.flush()
    return acct, await connect.fresh_link(acct)


# ── reconciliation ────────────────────────────────────────────────────────────

async def _period_balances(db: AsyncSession, country: str, start: date, end: date, week: WeekStatements) -> list[S.Balance]:
    """R23: each kitchen's balance for the period: the run's statements once it is prepared, else
    what a run prepared now would carry in (the same code)."""
    run_id = (await db.execute(select(PayoutRun.id).where(
        PayoutRun.country == country, PayoutRun.period_start == start, PayoutRun.period_end == end))).scalar()
    if run_id is None:
        from core_api.modules.payments.service import disputes as DS

        held = await DS.payout_adjustments(db, country)
        return list(kitchen_balances(week, await open_carries(db, country, start), start,
                                     {rid: sum(a.amount for a in adj) for rid, adj in held.items()}).values())
    stmts = (await db.execute(select(PayoutStatement).where(
        PayoutStatement.run_id == run_id, PayoutStatement.payee_type == "restaurant"))).scalars().all()
    return [S.Balance(s.amount - s.carried_in, s.carried_in, s.amount, s.negative_weeks, s.negative_since) for s in stmts]


async def to_collect(db: AsyncSession, country: str) -> list[dict]:
    """R23: kitchens whose balance has been below zero for COLLECT_AFTER_WEEKS weeks in a row or
    more (their latest statement, not carried on yet). Finance collects it by arrangement with the
    kitchen; nothing here or anywhere charges a kitchen. Longest first."""
    rows = (await db.execute(
        select(PayoutStatement, PayoutRun).join(PayoutRun, PayoutRun.id == PayoutStatement.run_id)
        .where(PayoutRun.country == country, PayoutStatement.payee_type == "restaurant", PayoutStatement.amount < 0,
               PayoutStatement.carried_to.is_(None), PayoutStatement.negative_weeks >= S.COLLECT_AFTER_WEEKS)
        .order_by(PayoutStatement.negative_weeks.desc(), PayoutStatement.amount))).all()
    return [{"restaurant_id": str(st.payee_id), "kitchen": st.payee_name, "currency": st.currency,
             "amount": -st.amount, "weeks": st.negative_weeks,
             "since": (st.negative_since or run.period_start).isoformat(), "statement_id": str(st.id),
             "run_id": str(run.id), "week_start": run.period_start.isoformat(), "week_end": run.period_end.isoformat()}
            for st, run in rows]

async def reconciliation(db: AsyncSession, country: str, start: date, end: date) -> dict:
    """Money in vs money owed for a period: orders, captured payments, refunds,
    tax, payouts, platform revenue; and anything that doesn't line up.

    R14: the money is the payout run's: the orders delivered in the period (each city's
    Monday to Monday) and the statements a run makes for them (week_statements). So
    "kitchens / delivery partners are owed" is what the run pays, minimum pay top-ups
    included, and platform revenue is what is left after them. R40 (the finance model): the
    restaurant pays the card fee for the whole charge, so it is its own line, out of the
    restaurants' money and never BhojanGo's:
        captured = refunded + restaurants owed + card fees + delivery partners owed + tax + BhojanGo.
    Order counts and issues stay per order placed in the period."""
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import PaymentIntent, Refund
    from core_api.modules.pricing.models import OrderPricingSnapshot

    c = await _country(db, country)
    payout_zone_name = str(payout_tz(c))
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

    # The money: the run's orders and statements (R14).
    week = await week_statements(db, country, start, end)
    week_ids = [uuid.UUID(o.order_id) for o in week.orders]
    week_snaps = {s.order_id: s for s in (await db.execute(select(OrderPricingSnapshot).where(
        OrderPricingSnapshot.order_id.in_(week_ids)))).scalars()} if week_ids else {}
    week_intents = (await db.execute(select(PaymentIntent).where(
        PaymentIntent.order_id.in_(week_ids), PaymentIntent.status.in_(("succeeded", "partially_refunded", "refunded"))))
    ).scalars().all() if week_ids else []
    week_refunds = (await db.execute(select(Refund).where(Refund.order_id.in_(week_ids)))).scalars().all() if week_ids else []

    def split_sum(key: str) -> Decimal:
        return S.m(sum((S.D(s.split.get(key, 0)) for s in week_snaps.values()), Decimal(0)))

    # R40: card fees as the restaurants' statements take them (the provider's actual fee once reported, else
    # the estimate); paid by restaurants, so they come out of the restaurants' money, never BhojanGo's.
    card_fees = week.kitchen_sum("card_fee")
    fee_reported = {i.order_id for i in week_intents if isinstance((i.metadata_ or {}).get("provider_fee"), int)}
    fees_estimated = sum(1 for oid in week_snaps if oid not in fee_reported)
    captured_total = sum(i.amount for i in week_intents)
    refunded_total = sum(r.amount for r in week_refunds if r.status not in ("failed", "rejected"))
    kitchens, riders, top_ups = week.restaurants_total, week.riders_total, week.top_ups
    # R16: tax owed by type: what customers paid (GST / sales tax), GST on our commission and TDS
    # (both taken from kitchen payouts; the platform owes them).
    tax_by_type = {"customer": split_sum("tax"), "commission": week.kitchen_sum("commission_tax"), "tds": week.kitchen_sum("tds")}
    tax = S.m(sum(tax_by_type.values(), Decimal(0)))
    platform = Decimal(captured_total - refunded_total) / 100 - kitchens - card_fees - riders - tax
    carry = carry_totals(await _period_balances(db, country, start, end, week))
    not_in_run = await _not_in_run(db, country, start, end, week)
    return {
        "country": country, "currency": c.currency, "period": {"start": start.isoformat(), "end": end.isoformat()},
        # R41: "delivered" is the week's orders as Contribution and the payout run count them: delivered between
        # Monday 00:00 and the next Monday 00:00 in the payout zone, by delivered time (review orders left out);
        # cancelled and still open are of the orders placed in the week.
        "orders": {"total": len(orders), "delivered": len(week.orders), "cancelled": sum(1 for o in orders if o.status == "cancelled"),
                   "open": sum(1 for o in orders if o.status not in ("delivered", "cancelled")),
                   "definition": f"Delivered between Monday 00:00 and Sunday 23:59 ({payout_zone_name}), by delivered time",
                   "placed": len(orders), "placed_delivered": len(delivered)},
        "money": {"captured": captured_total, "refunded": refunded_total, "net_collected": captured_total - refunded_total,
                  "delivered_gmv": S._minor_str(sum((S.D(s.total) for s in week_snaps.values()), Decimal(0))),
                  "tax_owed": S._minor_str(tax), "restaurant_payable": S._minor_str(kitchens),
                  # What the payout run pays delivery partners: trip pay, tips and the minimum pay top-ups.
                  "rider_payable": S._minor_str(riders), "min_pay_top_ups": S._minor_str(top_ups),
                  # R40: card fees, paid by restaurants (out of their food and packaging)
                  "card_fees": S._minor_str(card_fees),
                  # What BhojanGo keeps: platform fees less the offers and refunds it pays (and any top-ups).
                  "platform_revenue": S._minor_str(platform),
                  # R23: kitchens' balances below zero. "Kitchens are owed" is what the week's orders earned;
                  # the run nets in what earlier weeks left below zero and pays only what is above zero:
                  #   kitchens paid = kitchens are owed + carried from last week - carried to next week
                  "kitchen_carried_in": carry["carried_in"], "kitchen_carried_forward": carry["carried_forward"],
                  "restaurant_to_pay": carry["to_pay"]},
        "card_fees_estimated": fees_estimated,
        # R40: why "owed" and the payout run differ for the same week (None: no run yet, or it covers everything)
        "not_in_run": not_in_run,
        "tax_owed_by_type": {k: S._minor_str(v) for k, v in tax_by_type.items()},  # orders whose fee is the expected rate, not the provider's (R15)
        "by_provider": by_provider, "refunds_not_settled": pending_refunds,
        "issues": issues,
    }


async def _not_in_run(db: AsyncSession, country: str, start: date, end: date, week: WeekStatements) -> dict | None:
    """R40: the week's money that its payout run doesn't pay (yet), and why. "Owed" is worked out now from every
    order delivered in the week; the run is what was prepared earlier. Minor units."""
    run = (await db.execute(select(PayoutRun).where(
        PayoutRun.country == country, PayoutRun.period_start == start, PayoutRun.period_end == end))).scalars().first()
    if run is None:
        return None
    stmts = (await db.execute(select(PayoutStatement).where(PayoutStatement.run_id == run.id))).scalars().all()
    on_run = {ln.get("order_id") for st in stmts for ln in (st.lines or [])}
    late = [o.order_id for o in week.orders if o.order_id not in on_run]
    late_set = set(late)
    restaurants = sum((S.D(ln["net"]) for _, _, _, lines in week.restaurants for ln in lines if ln["order_id"] in late_set), Decimal(0))
    riders = sum((S.D(ln.get("total", ln.get("net", 0))) for _, _, _, lines, _ in week.riders for ln in lines
                  if ln.get("order_id") in late_set), Decimal(0))
    held = -sum((S.D(st.summary.get("disputes")) for st in stmts if st.payee_type == "restaurant"), Decimal(0))
    if not late and held == 0:
        return None
    return {"run_id": str(run.id), "orders": len(late), "restaurants": _minor(restaurants), "riders": _minor(riders),
            "reason": "Delivered after this payout run was prepared: they are paid with the next run" if late else None,
            "chargeback_holds": _minor(held)}
