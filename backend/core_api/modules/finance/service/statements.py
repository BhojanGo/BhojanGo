"""Payout statements, pure (no database): what each restaurant and rider earned.

Restaurant, per delivered order (from its pricing snapshot):
    food + packaging - commission - offers the restaurant funded
    (+ tax the restaurant collects itself)
    - item refunds that were the restaurant's fault (wrong or missing item,
      quality): the item's food value less the commission it paid on it.
      Delivery-fault and goodwill refunds are the platform's; they're listed
      on the statement for information only.

Rider, per delivered order:
    base + per km/mi x distance + waiting pay, + tip
  a later drop-off of a batch (item 2): no base; distance + waiting + the city's
  batch bonus, + tip
  and for the period a top-up to the hourly floor:
    floor x active hours - (base + distance + waiting)   if positive
  Engaged time = from accepting the offer to drop-off (driving to the
  restaurant and waiting there count), overlapping deliveries counted once.
  Tips never count towards the floor.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from shared.money import format_money

CENT = Decimal("0.01")
ZERO = Decimal(0)


def m(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def D(v: object) -> Decimal:
    return Decimal(str(v)) if v is not None else ZERO


@dataclass
class OrderForPayout:
    order_id: str
    delivered_at: datetime
    restaurant_id: str
    rider_id: str | None
    lines: list[dict]  # bill lines from the snapshot
    split: dict  # snapshot split (restaurant, rider, detail...)
    distance: Decimal
    rider_rule: dict | None  # rider_pay base_distance_wait params used for this order
    started_at: datetime | None  # when the rider accepted the offer (pickup for older orders)
    wait_minutes: Decimal = ZERO
    refund_lines: list[dict] = field(default_factory=list)  # refunded items (P12), each with "reason" and "fault"
    batch_position: int | None = None  # item 2: 2+ = a later drop-off of a batch
    batch_bonus: Decimal | None = None


def restaurant_statement(orders: list[OrderForPayout], commission_tax_pct: Decimal = ZERO,
                         tds_pct: Decimal = ZERO) -> tuple[Decimal, dict, list[dict]]:
    """R16: ``commission_tax_pct`` (India 18% GST on our commission) and ``tds_pct`` (section 194-O, a
    percent of the kitchen's gross sales: food and packaging) come off the kitchen's payout; the
    platform owes both to the government (Reconciliation's tax owed, by type)."""
    lines: list[dict] = []
    totals = {k: ZERO for k in ("food", "packaging", "commission", "commission_tax", "tds", "restaurant_funded_offers",
                                "restaurant_tax", "refunds")}
    for o in orders:
        amt = lambda code: sum((D(ln["amount"]) for ln in o.lines if ln["code"] == code), ZERO)  # noqa: E731
        food, packaging = amt("food"), amt("packaging")
        detail = o.split.get("detail", {})
        commission = D(detail.get("commission"))
        funded = D(detail.get("restaurant_funded_offers"))
        tax = D(detail.get("tax_collected_by_restaurant"))
        refund = ZERO
        theirs = [r for r in o.refund_lines if r.get("fault", "restaurant") == "restaurant"]
        if theirs and food > 0:
            keep = 1 - commission / food
            refund = m(sum((D(r["food"]) * keep for r in theirs), ZERO))
        refund_notes = [{"item": r.get("name", ""), "quantity": r.get("quantity", 1), "reason": r.get("reason", ""),
                         "fault": r.get("fault", "restaurant"),
                         "charged_to": "restaurant" if r.get("fault", "restaurant") == "restaurant" else "platform"}
                        for r in o.refund_lines]
        commission_tax = m(commission * D(commission_tax_pct) / 100)
        tds = m((food + packaging) * D(tds_pct) / 100)
        net = m(food + packaging - commission - commission_tax - tds - funded + tax - refund)
        lines.append({"order_id": o.order_id, "delivered_at": o.delivered_at.isoformat(), "food": str(food),
                      "packaging": str(packaging), "commission": str(-commission), "commission_tax": str(-commission_tax),
                      "tds": str(-tds), "restaurant_funded_offers": str(-funded),
                      "restaurant_tax": str(tax), "refunds": str(-refund), "refund_details": refund_notes,
                      "net": str(net)})
        for k, v in (("food", food), ("packaging", packaging), ("commission", commission), ("commission_tax", commission_tax),
                     ("tds", tds), ("restaurant_funded_offers", funded), ("restaurant_tax", tax), ("refunds", refund)):
            totals[k] += v
    total = m(sum((D(ln["net"]) for ln in lines), ZERO))
    summary = {"orders": len(orders), **{k: str(m(v)) for k, v in totals.items()}, "net": str(total),
               "commission_tax_percent": str(D(commission_tax_pct).normalize()), "tds_percent": str(D(tds_pct).normalize())}
    return total, summary, lines


def active_seconds(intervals: list[tuple[datetime, datetime]]) -> float:
    """Total time covered by the intervals; overlaps (batched orders) count once."""
    total, cur_start, cur_end = 0.0, None, None
    for start, end in sorted((s, e) for s, e in intervals if e > s):
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                total += (cur_end - cur_start).total_seconds()  # type: ignore[operator]
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    if cur_end is not None:
        total += (cur_end - cur_start).total_seconds()  # type: ignore[operator]
    return total


def rider_statement(orders: list[OrderForPayout], floor_per_hour: Decimal | None) -> tuple[Decimal, dict, list[dict]]:
    lines: list[dict] = []
    earned = {"base": ZERO, "distance": ZERO, "waiting": ZERO, "tips": ZERO}
    for o in orders:
        p = o.rider_rule or {}
        later = bool(o.batch_position and o.batch_position >= 2)  # item 2: no base, the batch bonus instead
        base = m(ZERO) if later else m(D(p.get("base")))
        bonus = m(D(o.batch_bonus)) if later else m(ZERO)
        dist = m(D(p.get("per_unit")) * o.distance)
        wait = m(D(p.get("per_wait_minute")) * max(ZERO, o.wait_minutes - D(p.get("free_wait_minutes", 0))))
        tip = m(D(o.split.get("detail", {}).get("tip")))
        lines.append({"order_id": o.order_id, "delivered_at": o.delivered_at.isoformat(), "base": str(base),
                      "distance": str(dist), "distance_units": str(o.distance), "waiting": str(wait), "tip": str(tip),
                      **({"batch_bonus": str(bonus), "batch_position": o.batch_position} if later else {}),
                      "total": str(base + bonus + dist + wait + tip)})
        earned["base"] += base + bonus
        earned["distance"] += dist
        earned["waiting"] += wait
        earned["tips"] += tip
    seconds = active_seconds([(o.started_at, o.delivered_at) for o in orders if o.started_at])
    hours = (Decimal(seconds) / 3600).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pay = earned["base"] + earned["distance"] + earned["waiting"]
    top_up = m(max(ZERO, (floor_per_hour or ZERO) * hours - pay)) if floor_per_hour else m(ZERO)
    total = m(pay + earned["tips"] + top_up)
    summary = {"deliveries": len(orders), **{k: str(m(v)) for k, v in earned.items()}, "active_hours": str(hours),
               "hourly_floor": str(floor_per_hour) if floor_per_hour else None, "floor_top_up": str(top_up),
               "per_active_hour": str(m(pay / hours)) if hours > 0 else None, "total": str(total)}
    return total, summary, lines


def _minor_str(v: Decimal) -> int:
    """Major units -> minor units (reports use minor units like payments)."""
    return int((m(v) * 100).to_integral_value())


# ── R23: a kitchen's week below zero is carried, never written off ─────────────
#
# A statement's amount is the week's net plus what earlier statements left below zero
# ("Carried from last week", <= 0). Below zero, nothing is paid and the whole balance moves
# to the payee's next statement; at zero nothing is paid and nothing moves; above zero the
# amount is paid (so next week's sales cover the balance first). The kitchen is never charged:
# from COLLECT_AFTER_WEEKS weeks below zero in a row, admin Finance lists it to collect from.
# Amounts here are minor units (ints), as on payout_statements.

COLLECT_AFTER_WEEKS = 4


@dataclass(frozen=True)
class Carry:
    """What a payee's earlier statements left below zero, brought into its next statement."""
    amount: int  # minor units, < 0
    weeks: int  # weeks below zero in a row so far
    since: date  # the Monday of the first of them
    statements: tuple[str, ...] = ()  # the statements it comes from


@dataclass(frozen=True)
class Balance:
    """A statement's amount with what it carries in, and where it leaves the payee."""
    net: int  # the week's own net, minor units
    carried_in: int  # <= 0
    amount: int  # net + carried_in: paid when above zero, carried again when below
    negative_weeks: int  # 0 unless amount < 0
    negative_since: date | None

    @property
    def to_pay(self) -> int:
        return max(self.amount, 0)

    @property
    def carried_forward(self) -> int:
        """What moves to the next statement (<= 0)."""
        return min(self.amount, 0)


def combine(carries: list[Carry]) -> Carry | None:
    """Several open balances (runs prepared out of order) brought in as one."""
    if not carries:
        return None
    return Carry(amount=sum(c.amount for c in carries), weeks=max(c.weeks for c in carries),
                 since=min(c.since for c in carries), statements=tuple(s for c in carries for s in c.statements))


# ── R24: what a statement below zero says ──────────────────────────────────────
#
# This week's own result W (amount - carried_in) and the balance B (amount) are said apart, and the
# amounts shown add up to |B|, the statement's total, never counting the carry twice:
#   W < 0:            "This week came to |W| below zero."
#   C < 0 (and W < 0): "Still |C| below zero from earlier weeks · carried to next week."
#   W >= 0, B < 0:     "Still |B| below zero from earlier weeks · carried to next week." (the week covered part)
#   W < 0, no carry:   the week line, then "Carried to next week."
# The same rule as the Kitchen app and admin (packages/ui/statement.js, belowZeroLines).

def below_zero_lines(amount: int, carried_in: int | None) -> list[tuple[str, int | None]]:
    """(kind, minor units below zero) for a statement's amount and carried_in: kind is "week",
    "earlier" or "carried" (no amount). Empty unless the amount is below zero."""
    if amount >= 0:
        return []
    c = min(carried_in or 0, 0)
    w = amount - c
    if w < 0:
        return [("week", -w), ("earlier", -c)] if c < 0 else [("week", -w), ("carried", None)]
    return [("earlier", -amount)]


BELOW_ZERO_TEXT = {"week": "This week came to {amount} below zero.",
                   "earlier": "Still {amount} below zero from earlier weeks · carried to next week.",
                   "carried": "Carried to next week."}
NEVER_FROM_BANK = "A week below zero pays nothing and carries to next week's statement; we never take it from your bank."


def below_zero_text(amount: int, carried_in: int | None, currency: str) -> list[str]:
    """The lines in English (the statement PDF), money formatted as everywhere else."""
    return [BELOW_ZERO_TEXT[kind].format(amount=format_money(Decimal(v) / 100, currency) if v is not None else "")
            for kind, v in below_zero_lines(amount, carried_in)]


def balance(net: int, carry: Carry | None, period_start: date) -> Balance:
    carried_in = carry.amount if carry else 0
    amount = net + carried_in
    if amount < 0:
        return Balance(net, carried_in, amount, (carry.weeks if carry else 0) + 1, carry.since if carry else period_start)
    return Balance(net, carried_in, amount, 0, None)


def settle(amount: int) -> str | None:
    """A statement with nothing to send: "carried" below zero (the balance moves to the next
    statement, never written off), "paid" at exactly zero. None: there is money to transfer."""
    if amount < 0:
        return "carried"
    if amount == 0:
        return "paid"
    return None


def to_collect(negative_weeks: int) -> bool:
    return negative_weeks >= COLLECT_AFTER_WEEKS


def major(minor: int) -> str:
    """Minor units -> "-12.34" (statement summaries and run totals are major-unit strings)."""
    return str(m(Decimal(minor) / 100))
