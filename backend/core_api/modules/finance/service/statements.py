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
  and for the period a top-up to the hourly floor:
    floor x active hours - (base + distance + waiting)   if positive
  Engaged time = from accepting the offer to drop-off (driving to the
  restaurant and waiting there count), overlapping deliveries counted once.
  Tips never count towards the floor.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

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


def restaurant_statement(orders: list[OrderForPayout]) -> tuple[Decimal, dict, list[dict]]:
    lines: list[dict] = []
    totals = {k: ZERO for k in ("food", "packaging", "commission", "restaurant_funded_offers", "restaurant_tax", "refunds")}
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
        net = m(food + packaging - commission - funded + tax - refund)
        lines.append({"order_id": o.order_id, "delivered_at": o.delivered_at.isoformat(), "food": str(food),
                      "packaging": str(packaging), "commission": str(-commission), "restaurant_funded_offers": str(-funded),
                      "restaurant_tax": str(tax), "refunds": str(-refund), "refund_details": refund_notes,
                      "net": str(net)})
        for k, v in (("food", food), ("packaging", packaging), ("commission", commission),
                     ("restaurant_funded_offers", funded), ("restaurant_tax", tax), ("refunds", refund)):
            totals[k] += v
    total = m(sum((D(ln["net"]) for ln in lines), ZERO))
    summary = {"orders": len(orders), **{k: str(m(v)) for k, v in totals.items()}, "net": str(total)}
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
        base = m(D(p.get("base")))
        dist = m(D(p.get("per_unit")) * o.distance)
        wait = m(D(p.get("per_wait_minute")) * max(ZERO, o.wait_minutes - D(p.get("free_wait_minutes", 0))))
        tip = m(D(o.split.get("detail", {}).get("tip")))
        lines.append({"order_id": o.order_id, "delivered_at": o.delivered_at.isoformat(), "base": str(base),
                      "distance": str(dist), "distance_units": str(o.distance), "waiting": str(wait), "tip": str(tip),
                      "total": str(base + dist + wait + tip)})
        earned["base"] += base
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
