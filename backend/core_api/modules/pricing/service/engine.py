"""The quote engine: the same 8 steps in every country (spec section 4).

    1 locate      (done by the caller: address -> zone -> city -> country, rules loaded)
    2 food        items + modifiers
    3 promotions  best food discount, plus free delivery; who funds each
    4 fees        delivery, service, small-order, packaging, surge, late-night
    5 taxes       each tax rule on its target lines
    6 tip
    7 total
    8 split       restaurant payout, rider pay, tax owed, platform revenue

Pure function over Decimals: no database, no clock (the caller passes the local
time). Every line is rounded half-up to the currency's minor unit as it is
computed, so the bill adds up exactly to what the customer pays.
"""
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from core_api.modules.rules.service.resolver import Candidate

CENT = Decimal("0.01")
ZERO = Decimal("0")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def money(v: Any) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)


def D(v: Any) -> Decimal:
    return Decimal(str(v))


class NotDeliverable(ValueError):
    """The order can't be quoted (too far, outside the zone...). Message is for customers."""


@dataclass(frozen=True)
class CartLine:
    name: str
    quantity: int
    unit_price: Decimal  # item price incl. chosen modifiers
    item_id: str | None = None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExternalTax:
    """Tax a provider calculated (US: Stripe Tax), one per jurisdiction."""

    label: str
    rate_percent: Decimal
    base: Decimal
    amount: Decimal
    jurisdiction: str
    provider: str
    calculation_id: str


@dataclass(frozen=True)
class QuoteInputs:
    currency: str
    lines: list[CartLine]
    distance: Decimal  # restaurant -> customer, in the country's unit (km or mi)
    local_time: datetime  # in the city's timezone
    tip: Decimal = ZERO
    restaurant_tier: str | None = None
    first_order: bool = False
    promo_code: str | None = None
    promo_spent: dict[str, Decimal] = field(default_factory=dict)  # rule_key -> spent so far
    promo_spent_week: dict[str, Decimal] = field(default_factory=dict)  # rule_key -> spent this week
    wait_minutes: Decimal = ZERO  # expected rider wait at the restaurant (rider pay)
    # None = not calculated yet (the quote is marked tax_pending); [] = no tax due.
    external_tax: list[ExternalTax] | None = None


@dataclass
class BillLine:
    code: str  # food | promotion | delivery_fee | service_fee | small_order_fee | packaging | surge | late_night_fee | tax | tip
    label: str
    amount: Decimal  # negative for discounts
    rule_id: str | None = None
    rule_version: int | None = None
    funded_by: str | None = None  # promotions
    taxable_as: str | None = None  # the tax target this line counts as
    detail: dict[str, str] | None = None  # taxes: rate, base, jurisdiction (the fair bill shows these)


@dataclass
class Split:
    restaurant: Decimal
    rider: Decimal
    tax: Decimal
    platform: Decimal
    detail: dict[str, Decimal]


@dataclass
class QuoteResult:
    currency: str
    lines: list[BillLine]
    food_subtotal: Decimal
    total: Decimal
    split: Split
    rules_used: list[dict[str, Any]]
    tax_pending: bool = False  # an external tax provider must still add tax (US, P9)

    def line(self, code: str) -> Decimal:
        return sum((ln.amount for ln in self.lines if ln.code == code), ZERO)


def _in_window(t: datetime, w: dict) -> bool:
    if DAYS[t.weekday()] not in w.get("days", DAYS):
        return False
    start = time.fromisoformat(w["start"])
    end = time.fromisoformat(w["end"])
    now = t.time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= now < end
    return now >= start or now < end  # wraps past midnight


def _ref(c: Candidate) -> dict[str, Any]:
    return {"rule_id": str(c.id), "rule_key": str(c.rule_key), "version": c.version, "slot": c.slot,
            "scope_level": c.scope_level, "scope_id": c.scope_id}


def taxable_amounts(q: "QuoteResult") -> dict[str, Decimal]:
    """Each taxable line's amount after discounts (what a tax provider is sent)."""
    out: dict[str, Decimal] = {}
    for ln in q.lines:
        if ln.taxable_as:
            out[ln.taxable_as] = out.get(ln.taxable_as, ZERO) + ln.amount
    return {k: money(v) for k, v in out.items() if v > 0}


def payment_fee(total: Decimal, method: str, params: dict | None, tax_calculated: bool = False) -> tuple[Decimal, dict[str, str]]:
    """What the payment provider keeps of a charge (business rule ``payment_fees``):
    percent + fixed for the method (``card`` for methods not listed), plus the tax
    service's percent when a provider calculated the tax. Nothing for cash."""
    if not params or method == "cash_on_delivery" or total <= 0:
        return ZERO, {}
    m = params["methods"].get(method) or params["methods"]["card"]
    processing = money(total * D(m["percent"]) / 100 + D(m.get("fixed", 0)))
    tax_service = money(total * D(params.get("tax_service_percent", 0)) / 100) if tax_calculated else ZERO
    return money(processing + tax_service), {"method": method, "processing": str(processing), "tax_service": str(tax_service),
                                             "percent": str(D(m["percent"])), "fixed": str(D(m.get("fixed", 0)))}


def compute(inp: QuoteInputs, rules: dict[str, Candidate]) -> QuoteResult:
    used: list[Candidate] = []
    lines: list[BillLine] = []

    def add(code: str, label: str, amount: Decimal, rule: Candidate | None = None, **kw: Any) -> BillLine:
        ln = BillLine(code, label, money(amount), str(rule.id) if rule else None, rule.version if rule else None, **kw)
        lines.append(ln)
        if rule is not None and rule not in used:
            used.append(rule)
        return ln

    def biz(template: str) -> Candidate | None:
        return rules.get(f"business:{template}")

    # ── guard rails ──────────────────────────────────────────────────────────
    if not inp.lines:
        raise NotDeliverable("Your bag is empty")
    radius = biz("max_radius")
    if radius:
        used.append(radius)  # it decided this order can be delivered
        if inp.distance > D(radius.params["distance"]):
            raise NotDeliverable("This restaurant is too far from your address")

    # ── 2 food ───────────────────────────────────────────────────────────────
    food = money(sum((ln.unit_price * ln.quantity for ln in inp.lines), ZERO))
    add("food", "Food", food, taxable_as="food")

    # ── 3 promotions ─────────────────────────────────────────────────────────
    def promo_ok(c: Candidate) -> bool:
        p = c.params
        if p.get("code") and p["code"] != (inp.promo_code or "").upper():
            return False
        if food < D(p.get("min_subtotal", 0)):
            return False
        if c.template == "first_order" and not inp.first_order:
            return False
        if p.get("budget_cap") is not None and inp.promo_spent.get(str(c.rule_key), ZERO) >= D(p["budget_cap"]):
            return False
        if p.get("weekly_cap") is not None and inp.promo_spent_week.get(str(c.rule_key), ZERO) >= D(p["weekly_cap"]):
            return False
        return True

    def promo_value(c: Candidate) -> Decimal:
        p = c.params
        if c.template in ("percent_off", "first_order"):
            v = food * D(p["percent"]) / 100
            if p.get("max_discount") is not None:
                v = min(v, D(p["max_discount"]))
        elif c.template in ("flat_off", "referral"):
            v = D(p["amount"])
        else:
            return ZERO
        if p.get("budget_cap") is not None:
            v = min(v, D(p["budget_cap"]) - inp.promo_spent.get(str(c.rule_key), ZERO))
        if p.get("weekly_cap") is not None:
            v = min(v, D(p["weekly_cap"]) - inp.promo_spent_week.get(str(c.rule_key), ZERO))
        return money(min(v, food))

    promos = [c for slot, c in rules.items() if slot.startswith("promotion:") and promo_ok(c)]
    discounts = sorted((c for c in promos if c.template != "free_delivery"), key=promo_value, reverse=True)
    discount = ZERO
    if discounts and promo_value(discounts[0]) > 0:
        best = discounts[0]
        discount = promo_value(best)
        add("promotion", best.name or "Offer", -discount, best, funded_by=best.params["funded_by"], taxable_as="food")
    free_delivery = next((c for c in promos if c.template == "free_delivery"), None)

    # ── 4 fees ───────────────────────────────────────────────────────────────
    fees: dict[str, Decimal] = {}
    dr = rules.get("delivery_fee")
    if dr is None:
        raise NotDeliverable("Delivery isn't set up here yet")
    p = dr.params
    if dr.template == "flat":
        delivery = D(p["amount"])
    elif dr.template == "distance_slabs":
        slab = next((s for s in p["slabs"] if inp.distance <= D(s["up_to"])), None)
        if slab is not None:
            delivery = D(slab["fee"])
        elif p.get("beyond_per_unit") is not None:
            last = p["slabs"][-1]
            delivery = D(last["fee"]) + (inp.distance - D(last["up_to"])) * D(p["beyond_per_unit"])
        else:
            used.append(dr)
            raise NotDeliverable("This restaurant is too far from your address")
    elif dr.template == "free_above":
        delivery = ZERO if food >= D(p["min_subtotal"]) else D(p["otherwise"])
    elif dr.template == "tier_base":
        delivery = D(p["tiers"].get(inp.restaurant_tier or p["default_tier"], p["tiers"][p["default_tier"]]))
    else:
        delivery = ZERO
    fees["delivery_fee"] = add("delivery_fee", "Delivery fee", delivery, dr, taxable_as="delivery_fee").amount
    if free_delivery is not None and fees["delivery_fee"] > 0:
        add("promotion", free_delivery.name or "Free delivery", -fees["delivery_fee"], free_delivery,
            funded_by=free_delivery.params["funded_by"], taxable_as="delivery_fee")

    sf = rules.get("customer_fee:service_fee")
    if sf:
        base = food - discount if sf.params.get("base") == "after_promotions" else food
        v = base * D(sf.params["percent"]) / 100
        v = max(D(sf.params["min"]), min(D(sf.params["max"]), v))
        fees["service_fee"] = add("service_fee", "Service fee", v, sf, taxable_as="service_fee").amount
    so = rules.get("customer_fee:small_order_fee")
    if so and food < D(so.params["below"]):
        fees["small_order_fee"] = add("small_order_fee", "Small order fee", D(so.params["fee"]), so,
                                      taxable_as="small_order_fee").amount
    pk = rules.get("customer_fee:packaging_levy")
    if pk and D(pk.params["amount"]) > 0:
        fees["packaging"] = add("packaging", "Packaging", D(pk.params["amount"]), pk, taxable_as="packaging").amount
    sg = rules.get("customer_fee:surge_levy")
    if sg and any(_in_window(inp.local_time, w) for w in sg.params["windows"]):
        fees["surge"] = add("surge", "Busy-hour fee", D(sg.params["amount"]), sg, taxable_as="surge").amount
    ln = rules.get("customer_fee:late_night_fee")
    if ln and _in_window(inp.local_time, ln.params["window"]):
        fees["late_night_fee"] = add("late_night_fee", "Late-night fee", D(ln.params["amount"]), ln,
                                     taxable_as="late_night_fee").amount

    # ── 5 taxes ──────────────────────────────────────────────────────────────
    tax_added = ZERO
    tax_owed = ZERO
    tax_by_collector: dict[str, Decimal] = {"platform": ZERO, "restaurant": ZERO}
    tax_pending = False
    line_order = ["food", "packaging", "delivery_fee", "service_fee", "small_order_fee", "surge", "late_night_fee"]

    def tax_order(slot: str) -> tuple[int, str]:
        targets = rules[slot].params.get("target_lines", [])
        return (min((line_order.index(x) for x in targets if x in line_order), default=99), slot)

    for slot in sorted((s for s in rules if s.startswith("tax:")), key=tax_order):
        t = rules[slot]
        if t.template == "external":
            used.append(t)
            if inp.external_tax is None:
                tax_pending = True
                continue
            external_targets = ",".join(sorted({bl.taxable_as for bl in lines if bl.taxable_as}))
            for ext in inp.external_tax:
                amount = add("tax", ext.label, ext.amount, t, detail={
                    "rate_percent": str(ext.rate_percent), "base": str(money(ext.base)), "jurisdiction": ext.jurisdiction,
                    "provider": ext.provider, "calculation_id": ext.calculation_id, "targets": external_targets}).amount
                tax_added += amount
                tax_owed += amount
                tax_by_collector["platform"] += amount  # marketplace facilitator: the platform collects
            continue
        tp = t.params
        targets = set(tp["target_lines"])
        base = sum(
            (bl.amount for bl in lines
             if bl.taxable_as in targets and (bl.code != "promotion" or tp.get("after_promotions", True))),
            ZERO,
        )
        rate = D(tp["rate_percent"]) / 100
        detail = {"rate_percent": str(D(tp["rate_percent"]).normalize()), "base": str(money(base)),
                  "collected_by": tp.get("collected_by", "platform"), "targets": ",".join(tp["target_lines"])}
        if tp.get("inclusive"):
            amount = money(base - base / (1 + rate))  # already inside the prices
            add("tax_included", f'{tp["label"]} (included in prices)', ZERO, t, detail={**detail, "included": str(amount)})
        else:
            amount = add("tax", tp["label"], base * rate, t, detail=detail).amount
            tax_added += amount
        tax_owed += amount
        tax_by_collector[tp.get("collected_by", "platform")] += amount

    # ── 6 tip ────────────────────────────────────────────────────────────────
    tip = money(inp.tip)
    if tip > 0:
        add("tip", "Tip for your rider", tip)

    # ── 7 total ──────────────────────────────────────────────────────────────
    total = money(sum((bl.amount for bl in lines), ZERO))

    # ── 8 split ──────────────────────────────────────────────────────────────
    restaurant_funded = -sum((bl.amount for bl in lines if bl.funded_by == "restaurant"), ZERO)
    commission = ZERO
    ct = rules.get("commission:rate")  # the most specific of restaurant > city > country
    if ct:
        from core_api.modules.rules.service.templates import commission_percent

        pct = commission_percent(ct.template, ct.params, inp.restaurant_tier)
        commission += money(food * pct / 100)
        used.append(ct)
    cf = rules.get("commission:flat_per_order")
    if cf:
        commission += money(D(cf.params["amount"]))
        used.append(cf)
    packaging = fees.get("packaging", ZERO)
    restaurant = money(food + packaging - commission - restaurant_funded + tax_by_collector["restaurant"])

    rider_base = ZERO
    rp = rules.get("rider_pay:base_distance_wait")
    if rp:
        rpp = rp.params
        wait = max(ZERO, inp.wait_minutes - D(rpp.get("free_wait_minutes", 0)))
        rider_base = money(D(rpp["base"]) + D(rpp["per_unit"]) * inp.distance + D(rpp.get("per_wait_minute", 0)) * wait)
        used.append(rp)
    rider = money(rider_base + tip)

    government = money(tax_by_collector["platform"])
    platform = money(total - restaurant - rider - government)
    split = Split(
        restaurant=restaurant, rider=rider, tax=money(tax_owed), platform=platform,
        detail={"commission": commission, "restaurant_funded_offers": money(restaurant_funded),
                "platform_funded_offers": money(-sum((bl.amount for bl in lines if bl.funded_by == "platform"), ZERO)),
                "rider_base": rider_base, "tip": tip, "tax_collected_by_restaurant": money(tax_by_collector["restaurant"])},
    )
    return QuoteResult(
        currency=inp.currency, lines=lines, food_subtotal=food, total=total, split=split,
        rules_used=[_ref(c) for c in used], tax_pending=tax_pending,
    )
