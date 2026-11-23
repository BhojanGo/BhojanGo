"""Fee model v2 (R29), pure: integer cents, half-up per line, and where each setting comes from.

    platform fee   = max(min_platform_fee, platform_fee_pct x food subtotal)      paid by the customer, to BhojanGo
    commission     = restaurant_commission_pct x food subtotal (default 0)         off the restaurant's payout
    payment fee    = card_fee_estimate for the payment method (R30: card, UPI, wallet, net banking; cash 0):
                     percent x (charge - tip) + fixed                                off the restaurant's payout
                     (production: the gateway's actual fee for the payment replaces it, from the webhook)
    delivery fee   = R31: distance bands on the road distance (template distance_slabs), up to the max delivery
                     distance (business:max_radius); 100% to the delivery partner;
                     tip = 100% to the delivery partner. Nothing tops the partner up from the platform fee.

Settings live in the rule engine (family ``fee`` and the ``commission:rate`` slot), one slot each, so each
inherits on its own: Country -> State/Region -> City -> Restaurant, the most specific published rule in
effect at that moment wins (rules.service.resolver). ``settings`` turns the resolved rules into values
plus where each came from ("Inherited from: USA") and is what an order snapshots at placement.
"""
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from core_api.modules.rules.service.resolver import Candidate

SLOTS = {
    "platform_fee_pct": "fee:platform_fee_pct",
    "min_platform_fee": "fee:min_platform_fee",
    "restaurant_commission_pct": "commission:rate",
    "card_fee_estimate": "fee:card_fee_estimate",
    "delivery_fee": "delivery_fee",  # R31: distance bands (R30's base + per km/mi still reads), every level
    "max_delivery_distance": "business:max_radius",  # R31: beyond it a restaurant doesn't deliver
    "pickup_platform_fee_pct": "fee:pickup_platform_fee_pct",  # R32: a pickup order's platform fee
    "gst_offer_base": "business:gst_offer_base",  # R32 (country): platform-funded offers reduce the GST base
}
CASH = "cash_on_delivery"
BHOJANGO_WALLET = "wallet"  # an order's "wallet": the customer's BhojanGo wallet, no gateway, no fee (R31)
# what a gateway reports for a payment (Razorpay "method") -> the estimate's method
GATEWAY_METHOD = {"card": "card", "upi": "upi", "wallet": "gateway_wallet", "netbanking": "net_banking",
                  "net_banking": "net_banking", "emi": "card", "paylater": "card"}
FIELDS = tuple(SLOTS)


def to_cents(v: Any) -> int:
    """A major-unit amount (``"3.99"``, Decimal) as integer cents, half-up."""
    return int((Decimal(str(v)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_cents(c: int) -> Decimal:
    return (Decimal(c) / 100).quantize(Decimal("0.01"))


def percent_of(cents: int, percent: Any) -> int:
    """``percent`` % of ``cents``, rounded half-up to a whole cent (3698 at 10% -> 370)."""
    if cents <= 0:
        return 0
    return int((Decimal(cents) * Decimal(str(percent)) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def platform_fee_cents(food_cents: int, percent: Any, min_cents: int = 0) -> int:
    """The customer's platform fee on the food subtotal, never below the minimum (6.00 at 10%, min 0.99 -> 0.99).
    No food, no fee."""
    if food_cents <= 0:
        return 0
    return max(percent_of(food_cents, percent), min_cents)


def method_rate(params: dict, method: str | None) -> dict | None:
    """The estimate's rate for a payment method: its own, else the card rate; None for cash and the BhojanGo
    wallet (no fee). ``gateway_wallet`` (a wallet inside the gateway's checkout) uses the "wallet" rate.
    Reads the R29 single-rate shape ``{percent, fixed}`` as the card rate."""
    if method in (CASH, BHOJANGO_WALLET):  # R31: the BhojanGo wallet has no gateway, so no fee
        return None
    if "card" not in params:
        return {"percent": params["percent"], "fixed": params.get("fixed", 0)}
    key = "wallet" if method == "gateway_wallet" else (method or "card")  # a gateway's wallet (Paytm...): "wallet" rate
    return params.get(key) or params["card"]


def card_fee_cents(charge_cents: int, tip_cents: int, percent: Any, fixed_cents: int) -> int:
    """The card fee estimate on what the customer is charged, less the tip (46.89 at 2.9% + 0.30 -> 1.66)."""
    base = max(0, charge_cents - tip_cents)
    if base <= 0:
        return 0
    return percent_of(base, percent) + fixed_cents


@dataclass(frozen=True)
class Source:
    level: str  # country | region | city | restaurant (platform for a platform-wide default)
    scope_id: str
    rule_id: str
    version: int


@dataclass(frozen=True)
class Setting:
    value: dict[str, Any] | None  # e.g. {"percent": "10"}; None: no rule at any level
    source: Source | None

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "source": asdict(self.source) if self.source else None}


def _num(v: Any) -> str:
    """10 -> "10", 2.90 -> "2.9" (never "1E+1")."""
    return format(Decimal(str(v)).normalize(), "f")


def _money(v: Any) -> str:
    return str(Decimal(str(v)).quantize(Decimal("0.01")))


def _value(field: str, c: Candidate, tier: str | None) -> dict[str, Any]:
    p = c.params
    if field == "restaurant_commission_pct":
        from core_api.modules.rules.service.templates import commission_percent

        return {"percent": _num(commission_percent(c.template, p, tier))}
    if field == "card_fee_estimate":
        out = {}
        for m in ("card", "upi", "wallet", "net_banking"):
            r = method_rate(p, m) if (m == "card" or p.get(m)) else None
            if r:
                out[m] = {"percent": _num(r["percent"]), "fixed": _money(r.get("fixed", 0))}
        return out
    if field == "delivery_fee":
        if c.template == "distance_slabs":
            return {"bands": [{"up_to": _num(b["up_to"]), "fee": _money(b["fee"])} for b in p["slabs"]],
                    **({"beyond_per_unit": _money(p["beyond_per_unit"])} if p.get("beyond_per_unit") is not None else {})}
        if c.template == "base_per_distance":
            return {"base": _money(p["base"]), "per_unit": _money(p["per_unit"])}
        return {"template": c.template}  # another delivery fee shape (flat, free above...): shown by name
    if field == "max_delivery_distance":
        return {"distance": _num(p["distance"])}
    if field == "gst_offer_base":
        return {"on": "true" if p.get("platform_offers_reduce_base") else "false"}
    if field == "min_platform_fee":
        return {"amount": _money(p["amount"])}
    return {"percent": _num(p["percent"])}


def settings(resolved: dict[str, Candidate], tier: str | None = None) -> dict[str, Setting]:
    """Each fee setting's effective value and the rule (level, scope) it comes from."""
    out: dict[str, Setting] = {}
    for field, slot in SLOTS.items():
        c = resolved.get(slot)
        out[field] = Setting(
            value=_value(field, c, tier) if c else None,
            source=Source(level=c.scope_level, scope_id=c.scope_id, rule_id=str(c.id), version=c.version) if c else None,
        )
    return out


def snapshot(resolved: dict[str, Candidate], tier: str | None = None) -> dict[str, Any]:
    """What an order keeps at placement, so later rule changes never alter it."""
    return {"model": "v2", **{f: s.as_dict() for f, s in settings(resolved, tier).items()}}
