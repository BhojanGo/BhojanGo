"""Rule templates (docs/specs/01-structure.md, section 3).

Admins never write formulas: each rule picks a template and fills in its
parameters, which are validated by the template's model below. Amounts are in
the country's currency (major units, e.g. 35.00 = ₹35), percentages are 0-100,
times are local HH:MM, distances use the country's unit (km or mi).

A *slot* is what rules compete for: for each slot the resolver takes the most
specific active rule. Delivery fee has one slot (one fee per order, whichever
template). Every other template is its own slot, and a rule may add a ``key``
when several of the same template apply together (e.g. GST on food and GST
on fees).
"""
import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
Money = Decimal
Pct = Field(ge=0, le=100)


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _hhmm(v: str) -> str:
    if not HHMM.match(v):
        raise ValueError("Use 24-hour HH:MM")
    return v


class TimeWindow(_P):
    start: str = Field(examples=["19:00"])
    end: str = Field(examples=["21:30"], description="May be after midnight (wraps)")
    days: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(
        default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    )
    @field_validator("start", "end")
    @classmethod
    def hhmm(cls, v: str) -> str:
        return _hhmm(v)


# ── Delivery fee ──────────────────────────────────────────────────────────────

class DeliveryFlat(_P):
    amount: Money = Field(ge=0)


class Slab(_P):
    up_to: Decimal = Field(gt=0, description="Distance up to and including this many km/mi")
    fee: Money = Field(ge=0)


class DeliveryDistanceSlabs(_P):
    slabs: list[Slab] = Field(min_length=1)
    beyond_per_unit: Money | None = Field(default=None, ge=0, description="Per km/mi past the last slab; None = not delivered")

    @model_validator(mode="after")
    def ascending(self) -> "DeliveryDistanceSlabs":
        ups = [s.up_to for s in self.slabs]
        if ups != sorted(ups) or len(set(ups)) != len(ups):
            raise ValueError("Slabs must go up in distance, without repeats")
        return self


class DeliveryFreeAbove(_P):
    min_subtotal: Money = Field(gt=0, description="Free delivery at or above this food subtotal")
    otherwise: Money = Field(ge=0, description="Fee below the threshold")


class DeliveryTierBase(_P):
    tiers: dict[str, Money] = Field(min_length=1, examples=[{"A": 25, "B": 30, "C": 40}])
    default_tier: str

    @model_validator(mode="after")
    def tier_known(self) -> "DeliveryTierBase":
        if self.default_tier not in self.tiers:
            raise ValueError("default_tier must be one of the tiers")
        return self


# ── Other customer fees ───────────────────────────────────────────────────────

class ServiceFee(_P):
    percent: Decimal = Pct
    min: Money = Field(ge=0)
    max: Money = Field(ge=0)
    base: Literal["food_subtotal", "after_promotions"] = "food_subtotal"

    @model_validator(mode="after")
    def bounds(self) -> "ServiceFee":
        if self.max < self.min:
            raise ValueError("max must be at least min")
        return self


class SmallOrderFee(_P):
    below: Money = Field(gt=0, description="Charged when the food subtotal is below this")
    fee: Money = Field(ge=0)


class PackagingLevy(_P):
    amount: Money = Field(ge=0, description="Per order")


class SurgeLevy(_P):
    windows: list[TimeWindow] = Field(min_length=1)
    amount: Money = Field(ge=0)


class LateNightFee(_P):
    window: TimeWindow
    amount: Money = Field(ge=0)


# ── Tax ───────────────────────────────────────────────────────────────────────

TaxLine = Literal["food", "packaging", "delivery_fee", "service_fee", "small_order_fee", "surge", "late_night_fee"]


class TaxRateOnLines(_P):
    label: str = Field(min_length=2, examples=["GST on food"])
    rate_percent: Decimal = Pct
    target_lines: list[TaxLine] = Field(min_length=1)
    collected_by: Literal["platform", "restaurant"] = "platform"
    inclusive: bool = False
    after_promotions: bool = Field(default=True, description="Tax food after the discount")


class TaxExternal(_P):
    """US: rates come from Stripe Tax per order (P9)."""

    provider: Literal["stripe_tax"] = "stripe_tax"
    collected_by: Literal["platform"] = "platform"


# ── Commission ────────────────────────────────────────────────────────────────

class CommissionByTier(_P):
    tiers: dict[str, Decimal] = Field(min_length=1, examples=[{"A": 18, "B": 15, "C": 12}])
    default_tier: str
    base: Literal["food_subtotal"] = "food_subtotal"

    @model_validator(mode="after")
    def tier_known(self) -> "CommissionByTier":
        if self.default_tier not in self.tiers:
            raise ValueError("default_tier must be one of the tiers")
        if any(not (0 <= v <= 100) for v in self.tiers.values()):
            raise ValueError("Commission is a percentage between 0 and 100")
        return self


class CommissionFlat(_P):
    amount: Money = Field(ge=0, description="Per order, on top of the percentage")


class PayoutSchedule(_P):
    frequency: Literal["weekly", "biweekly"] = "weekly"
    day: Literal["mon", "tue", "wed", "thu", "fri"] = "mon"
    hold_days: int = Field(default=2, ge=0, le=14)


# ── Rider pay ─────────────────────────────────────────────────────────────────

class RiderBaseDistanceWait(_P):
    base: Money = Field(ge=0)
    per_unit: Money = Field(ge=0, description="Per km/mi, restaurant to customer")
    per_wait_minute: Money = Field(default=Decimal("0"), ge=0)
    free_wait_minutes: int = Field(default=5, ge=0)


class RiderHourlyFloor(_P):
    per_active_hour: Money = Field(gt=0, description="Weekly top-up so active hours earn at least this")


class RiderBatchBonus(_P):
    per_extra_order: Money = Field(ge=0)


class RiderPeakBonus(_P):
    windows: list[TimeWindow] = Field(min_length=1)
    per_order: Money = Field(ge=0)


# ── Business rules ────────────────────────────────────────────────────────────

class AcceptTimeout(_P):
    seconds: int = Field(ge=30, le=1800)


class UnpaidAutoCancel(_P):
    minutes: int = Field(ge=1, le=120)


class CancelWindow(_P):
    minutes: int = Field(ge=0, le=60, description="Customer can cancel free of charge this long after placing")


class RefundWindow(_P):
    hours: int = Field(ge=1, le=720)


class CodLimit(_P):
    max_amount: Money = Field(ge=0, description="0 = cash on delivery off")


class TipPresets(_P):
    amounts: list[Money] = Field(min_length=1, max_length=5)
    default_index: int | None = Field(default=None, ge=0)


class MaxRadius(_P):
    distance: Decimal = Field(gt=0, description="km/mi from restaurant to customer")


class DispatchOfferTimeout(_P):
    seconds: int = Field(ge=10, le=120)


class SupportRefundLimit(_P):
    """The most a support agent may refund on one order (P12); above it, a
    city ops, country manager or finance admin does it."""

    max_per_order: Money = Field(ge=0)


class AutoRefundLimit(_P):
    """B5: a customer's problem report is refunded at once up to this much per
    order; above it, it goes to support as a ticket."""

    max_per_order: Money = Field(ge=0)


# ── Promotions ────────────────────────────────────────────────────────────────

class _Promo(_P):
    funded_by: Literal["platform", "restaurant"]
    budget_cap: Money | None = Field(default=None, gt=0, description="Stop when this much has been given away")
    weekly_cap: Money | None = Field(default=None, gt=0, description="Stop each week (Monday, market time) at this much")
    min_subtotal: Money = Field(default=Decimal("0"), ge=0)
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9]{3,20}$", description="None = applies automatically")


class PromoPercentOff(_Promo):
    percent: Decimal = Field(gt=0, le=100)
    max_discount: Money | None = Field(default=None, gt=0)


class PromoFlatOff(_Promo):
    amount: Money = Field(gt=0)


class PromoFreeDelivery(_Promo):
    pass


class PromoFirstOrder(_Promo):
    percent: Decimal = Field(gt=0, le=100)
    max_discount: Money | None = Field(default=None, gt=0)


class PromoReferral(_Promo):
    amount: Money = Field(gt=0)


# ── Registry ──────────────────────────────────────────────────────────────────

FAMILIES = ("delivery_fee", "customer_fee", "tax", "commission", "rider_pay", "business", "promotion")
MONEY_FAMILIES = frozenset(FAMILIES) - {"business"}

LEVELS = ("platform", "country", "region", "city", "zone", "restaurant")
ALLOWED_LEVELS: dict[str, frozenset[str]] = {
    "delivery_fee": frozenset({"city", "zone", "restaurant"}),
    "customer_fee": frozenset({"city", "zone", "restaurant"}),
    "tax": frozenset({"country", "region", "city"}),
    "commission": frozenset({"country", "city", "restaurant"}),
    "rider_pay": frozenset({"country", "region", "city"}),
    "business": frozenset({"platform", "country", "city"}),
    "promotion": frozenset({"country", "city", "restaurant"}),
}

TEMPLATES: dict[str, dict[str, type[BaseModel]]] = {
    "delivery_fee": {
        "flat": DeliveryFlat,
        "distance_slabs": DeliveryDistanceSlabs,
        "free_above": DeliveryFreeAbove,
        "tier_base": DeliveryTierBase,
    },
    "customer_fee": {
        "service_fee": ServiceFee,
        "small_order_fee": SmallOrderFee,
        "packaging_levy": PackagingLevy,
        "surge_levy": SurgeLevy,
        "late_night_fee": LateNightFee,
    },
    "tax": {"rate_on_lines": TaxRateOnLines, "external": TaxExternal},
    "commission": {"percent_by_tier": CommissionByTier, "flat_per_order": CommissionFlat, "payout_schedule": PayoutSchedule},
    "rider_pay": {
        "base_distance_wait": RiderBaseDistanceWait,
        "hourly_floor": RiderHourlyFloor,
        "batch_bonus": RiderBatchBonus,
        "peak_bonus": RiderPeakBonus,
    },
    "business": {
        "accept_timeout": AcceptTimeout,
        "unpaid_auto_cancel": UnpaidAutoCancel,
        "cancel_window": CancelWindow,
        "refund_window": RefundWindow,
        "cod_limit": CodLimit,
        "tip_presets": TipPresets,
        "max_radius": MaxRadius,
        "dispatch_offer_timeout": DispatchOfferTimeout,
        "support_refund_limit": SupportRefundLimit,
        "auto_refund_limit": AutoRefundLimit,
    },
    "promotion": {
        "percent_off": PromoPercentOff,
        "flat_off": PromoFlatOff,
        "free_delivery": PromoFreeDelivery,
        "first_order": PromoFirstOrder,
        "referral": PromoReferral,
    },
}

KEY_RE = re.compile(r"^[a-z0-9_]{2,40}$")


class TemplateError(ValueError):
    pass


def validate_params(family: str, template: str, params: dict) -> dict:
    """Validate against the template; returns the normalised params (JSON-ready)."""
    if family not in TEMPLATES:
        raise TemplateError(f"Unknown rule family {family!r}")
    model = TEMPLATES[family].get(template)
    if model is None:
        raise TemplateError(f"{family} has no template {template!r}; pick one of {', '.join(TEMPLATES[family])}")
    return model.model_validate(params).model_dump(mode="json")


def slot_for(family: str, template: str, key: str | None) -> str:
    if family == "delivery_fee":
        return "delivery_fee"
    if family == "promotion":
        # Every promotion is its own slot: several offers can be live at once.
        return f"promotion:{template}:{key or 'default'}"
    return f"{family}:{template}" + (f":{key}" if key else "")


def check_key(key: str | None) -> None:
    if key is not None and not KEY_RE.match(key):
        raise TemplateError("key: 2-40 lowercase letters, digits or _")


def catalogue() -> list[dict]:
    """What the admin console shows when someone adds a rule."""
    return [
        {
            "family": family,
            "template": name,
            "money": family in MONEY_FAMILIES,
            "allowed_levels": sorted(ALLOWED_LEVELS[family], key=LEVELS.index),
            "params_schema": model.model_json_schema(),
        }
        for family, templates in TEMPLATES.items()
        for name, model in templates.items()
    ]
