"""Contribution per order (item 1): what the platform keeps, per city, for a period.

For each delivered order, from its pricing snapshot:

    commission + customer fees (delivery, service, small-order, busy-hour, late-night)
  - offers the platform funded
  - rider pay (base + distance + waiting; tips are the rider's, not ours)
  = platform (the snapshot's split)
  - payment fees (what Stripe / Razorpay keep: the ``payment_fees`` rule at order time)
  - refunds the platform pays (everything refunded on the order, less what the kitchen
    is charged for its own mistakes: the same rule as payout statements)
  = platform keeps

Orders priced before payment fees were recorded get them worked out from the rule in
force now and the order's payment method; they're counted in ``fees_estimated``.
The hourly-floor top-up is paid per week, not per order, so it isn't in here.
"""
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.service import statements as S

FEE_CODES = ("delivery_fee", "service_fee", "small_order_fee", "surge", "late_night_fee")
FIELDS = ("gmv", "commission", "customer_fees", "platform_promos", "rider_pay", "platform", "payment_fees", "refunds", "keeps")


async def contribution(db: AsyncSession, scope: str, start: date, end: date) -> dict:
    from core_api.modules.finance.service.payouts import _country, _in_period
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import Refund
    from core_api.modules.pricing.models import OrderPricingSnapshot
    from core_api.modules.pricing.service.engine import payment_fee
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    country = scope[:2]
    c = await _country(db, country)
    rows = (await db.execute(
        select(Order, OrderPricingSnapshot).join(OrderPricingSnapshot, OrderPricingSnapshot.order_id == Order.id)
        .where(Order.status == "delivered", Order.market_city.like(f"{scope}%" if len(scope) > 2 else f"{scope}-%"),
               await _in_period(db, country, start, end, Order.actual_delivery_time))
    )).all()
    ids = [o.id for o, _ in rows]
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
    rules_now: dict[str, dict | None] = {}
    by_city: dict[str, dict[str, Decimal]] = defaultdict(lambda: {k: Decimal(0) for k in FIELDS})
    counts: dict[str, int] = defaultdict(int)
    estimated = 0
    for o, snap in rows:
        split, detail = snap.split, snap.split.get("detail", {})
        amt = lambda *codes: sum((S.D(ln["amount"]) for ln in snap.lines if ln["code"] in codes), Decimal(0))  # noqa: E731
        platform = S.D(split.get("platform"))
        if "payment_fees" in split:
            fees = S.D(split["payment_fees"])
        else:  # priced before fees were recorded: the rule in force now, the order's method
            city = o.market_city or ""
            if city not in rules_now:
                r = (await RuleService(db).resolve(Context(country=city[:2], region=city[:5], city=city))).get("business:payment_fees")
                rules_now[city] = r.params if r else None
            tax_calc = any((ln.get("detail") or {}).get("provider") for ln in snap.lines if ln["code"] == "tax")
            fees, _ = payment_fee(S.D(snap.total), o.payment_method or "card", rules_now[city], tax_calc)
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
        b["rider_pay"] += S.D(detail.get("rider_base"))
        b["platform"] += platform
        b["payment_fees"] += fees
        b["refunds"] += platform_refunds
        b["keeps"] += platform - fees - platform_refunds
        counts[o.market_city or "?"] += 1

    def out(code: str, n: int, v: dict[str, Decimal]) -> dict:
        return {"city": code, "orders": n, "totals": {k: str(S.m(x)) for k, x in v.items()},
                "per_order": {k: str(S.m(x / n)) if n else None for k, x in v.items()}}

    cities = [out(code, counts[code], v) for code, v in sorted(by_city.items())]
    total = {k: sum((v[k] for v in by_city.values()), Decimal(0)) for k in FIELDS}
    n = sum(counts.values())
    return {"scope": scope, "currency": c.currency, "period": {"start": start.isoformat(), "end": end.isoformat()},
            "cities": cities, "all": out(scope, n, total), "fees_estimated": estimated}
