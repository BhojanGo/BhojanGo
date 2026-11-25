"""Contribution per order (item 1): what the platform keeps, per city, for a period.

For each delivered order, from its pricing snapshot:

    commission + customer fees (delivery, service, small-order, busy-hour, late-night)
  - offers the platform funded
  - rider pay (base + distance + waiting; tips are the rider's, not ours)
  = platform (the snapshot's split)
  - refunds the platform pays (everything refunded on the order, less what the kitchen
    is charged for its own mistakes: the same rule as payout statements)
  - minimum pay top-ups (R14): what the week's payout run adds so a delivery partner's
    active hours earn the city's minimum; each partner's top-up is shared evenly across
    their orders that week (payouts.week_statements, the run's own numbers)
  = platform keeps

R40 (the finance model): the restaurant pays the card/payment fee for the whole charge; BhojanGo pays
no payment fees. ``card_fees`` is shown for information (paid by restaurants, never taken from what
BhojanGo keeps): the order's card fee as its restaurant statement takes it (production: the provider's
actual fee once reported; else the estimate, counted in ``fees_estimated``).
"""
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.service import statements as S

FEE_CODES = ("delivery_fee", "platform_fee", "service_fee", "small_order_fee", "surge", "late_night_fee")
FIELDS = ("gmv", "commission", "customer_fees", "platform_promos", "rider_pay", "platform", "card_fees", "refunds",
          "min_pay_top_ups", "keeps")


async def contribution(db: AsyncSession, scope: str, start: date, end: date, order_ids: list[str] | None = None) -> dict:
    """``order_ids``: only these orders (the soak reports exactly the orders it placed)."""
    from core_api.modules.finance.service.payouts import (
        _country,
        _in_period,
        week_statements,
    )
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import Refund
    from core_api.modules.pricing.models import OrderPricingSnapshot

    country = scope[:2]
    c = await _country(db, country)
    rows = (await db.execute(
        select(Order, OrderPricingSnapshot).join(OrderPricingSnapshot, OrderPricingSnapshot.order_id == Order.id)
        .where(Order.status == "delivered", Order.market_city.like(f"{scope}%" if len(scope) > 2 else f"{scope}-%"),
               await _in_period(db, country, start, end, Order.actual_delivery_time),
               *([Order.id.in_([uuid.UUID(i) for i in order_ids])] if order_ids is not None else []))
    )).all()
    ids = [o.id for o, _ in rows]
    from core_api.modules.payments.models.payment import PaymentIntent

    actual_fee: dict[uuid.UUID, Decimal] = {}  # what the provider reported it kept (minor units -> major)
    if ids:
        for pi in (await db.execute(select(PaymentIntent).where(
                PaymentIntent.order_id.in_(ids), PaymentIntent.status.in_(("succeeded", "partially_refunded", "refunded"))))).scalars():
            if isinstance((pi.metadata_ or {}).get("provider_fee"), int):
                actual_fee[pi.order_id] = actual_fee.get(pi.order_id, Decimal(0)) + Decimal(pi.metadata_["provider_fee"]) / 100
    refunded: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    refund_lines: dict[uuid.UUID, list[dict]] = defaultdict(list)
    if ids:
        for r in (await db.execute(select(Refund).where(Refund.order_id.in_(ids)))).scalars():
            if r.status in ("failed", "rejected"):
                continue
            refunded[r.order_id] += Decimal(r.amount) / 100  # minor units
            if r.kind == "items":
                refund_lines[r.order_id] += [{**ln, "reason": r.reason, "fault": r.fault or "restaurant"}
                                             for ln in r.lines if ln.get("menu_item_id")]
    top_up_of = (await week_statements(db, country, start, end)).top_up_per_order()
    # Item 2: a later drop-off of a batch pays no base but the batch bonus; the split was
    # priced before the batch, so the base comes from the order's own rider pay rule.
    from core_api.modules.rules.models import Rule

    rider_slot = "rider_pay:base_distance_wait"
    rider_rule_ids = {uuid.UUID(v["rule_id"]) for o, snap in rows if (o.batch_position or 0) >= 2
                      for v in snap.rule_versions if v["slot"] == rider_slot}
    rider_rules = ({str(r.id): r.params for r in (await db.execute(select(Rule).where(Rule.id.in_(rider_rule_ids)))).scalars()}
                   if rider_rule_ids else {})
    by_city: dict[str, dict[str, Decimal]] = defaultdict(lambda: {k: Decimal(0) for k in FIELDS})
    counts: dict[str, int] = defaultdict(int)
    estimated = 0
    for o, snap in rows:
        split, detail = snap.split, snap.split.get("detail", {})
        amt = lambda *codes: sum((S.D(ln["amount"]) for ln in snap.lines if ln["code"] in codes), Decimal(0))  # noqa: E731
        platform = S.D(split.get("platform"))
        # R40: the card fee is the restaurant's (its statement takes it); BhojanGo pays none.
        fees = S.D(o.card_fee if o.card_fee is not None else detail.get("card_fee"))
        if o.id not in actual_fee:
            estimated += 1
        _, _, kitchen = S.restaurant_statement([S.OrderForPayout(
            order_id=str(o.id), delivered_at=o.actual_delivery_time, restaurant_id=str(o.restaurant_id), rider_id=None,
            lines=snap.lines, split=split, distance=Decimal(0), rider_rule=None, started_at=None,
            refund_lines=refund_lines.get(o.id, []))])
        kitchen_charged = -S.D(kitchen[0]["refunds"])
        platform_refunds = max(Decimal(0), refunded.get(o.id, Decimal(0)) - kitchen_charged)
        b = by_city[o.market_city or "?"]
        b["gmv"] += S.D(snap.total)
        b["commission"] += S.D(detail.get("commission"))
        b["customer_fees"] += amt(*FEE_CODES)
        b["platform_promos"] += S.D(detail.get("platform_funded_offers"))
        if "delivery_fee_to_partner" in detail:  # R29: the delivery fee, plus any guaranteed-pay top-up
            b["rider_pay"] += S.D(detail["delivery_fee_to_partner"]) + S.D(detail.get("rider_top_up"))
        elif (o.batch_position or 0) >= 2:
            rp = next((rider_rules.get(v["rule_id"]) for v in snap.rule_versions if v["slot"] == rider_slot), None) or {}
            platform += S.D(rp.get("base")) - S.D(o.batch_bonus)  # what the platform pays differs by base - bonus
            b["rider_pay"] += S.D(detail.get("rider_base")) - S.D(rp.get("base")) + S.D(o.batch_bonus)
        else:
            b["rider_pay"] += S.D(detail.get("rider_base"))
        b["platform"] += platform
        b["card_fees"] += fees
        b["refunds"] += platform_refunds
        top_up = top_up_of.get(str(o.id), Decimal(0))
        b["min_pay_top_ups"] += top_up
        b["keeps"] += platform - platform_refunds - top_up
        counts[o.market_city or "?"] += 1

    def out(code: str, n: int, v: dict[str, Decimal]) -> dict:
        return {"city": code, "orders": n, "totals": {k: str(S.m(x)) for k, x in v.items()},
                "per_order": {k: str(S.m(x / n)) if n else None for k, x in v.items()}}

    cities = [out(code, counts[code], v) for code, v in sorted(by_city.items())]
    total = {k: sum((v[k] for v in by_city.values()), Decimal(0)) for k in FIELDS}
    n = sum(counts.values())
    return {"scope": scope, "currency": c.currency, "period": {"start": start.isoformat(), "end": end.isoformat()},
            "cities": cities, "all": out(scope, n, total), "fees_estimated": estimated, "fees_actual": n - estimated}
