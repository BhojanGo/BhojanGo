"""Driver earnings protection — pure calculation module.

No I/O so it is trivial to unit-test. Money is exact Decimal in major units.

Pay model:
  base      = active-time pay + waiting-time pay + mileage pay + per-order (batch) bonus
  floor     = guaranteed minimum from logged-in/available time
  floor_topup = max(0, floor - base)            # tips never count toward the floor
  gross     = base + floor_topup + tips
  net       = gross - deductions
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class EarningsConfig:
    """Per-market payout rates (overridable)."""

    floor_per_hour: Decimal = Decimal("12.00")       # minimum guaranteed pay per available hour
    per_mile: Decimal = Decimal("0.65")              # mileage payout
    per_active_minute: Decimal = Decimal("0.25")     # active delivery time
    per_waiting_minute: Decimal = Decimal("0.15")    # waiting/idle time on a delivery
    per_order_bonus: Decimal = Decimal("1.50")       # batch complexity (per order in a batch)


@dataclass(frozen=True)
class EarningsResult:
    available_minutes: int
    active_minutes: int
    waiting_minutes: int
    miles: Decimal
    num_orders: int
    active_payout: Decimal
    waiting_time_payout: Decimal
    mileage_payout: Decimal
    order_bonus: Decimal
    floor_guarantee: Decimal
    floor_topup: Decimal
    tips: Decimal
    gross_earnings: Decimal
    deductions: Decimal
    net_earnings: Decimal

    def to_dict(self) -> dict:
        return {
            "available_minutes": self.available_minutes,
            "active_minutes": self.active_minutes,
            "waiting_minutes": self.waiting_minutes,
            "miles": float(self.miles),
            "num_orders": self.num_orders,
            "active_payout": float(self.active_payout),
            "waiting_time_payout": float(self.waiting_time_payout),
            "mileage_payout": float(self.mileage_payout),
            "order_bonus": float(self.order_bonus),
            "floor_guarantee": float(self.floor_guarantee),
            "floor_topup": float(self.floor_topup),
            "tips": float(self.tips),
            "gross_earnings": float(self.gross_earnings),
            "deductions": float(self.deductions),
            "net_earnings": float(self.net_earnings),
        }


def floor_pay(available_minutes: int, floor_per_hour: Decimal) -> Decimal:
    """Minimum guaranteed pay for the time a driver was logged-in and available."""
    return _money(Decimal(max(0, available_minutes)) / Decimal(60) * Decimal(str(floor_per_hour)))


def mileage_payout(miles: object, per_mile: Decimal) -> Decimal:
    return _money(Decimal(str(miles)) * Decimal(str(per_mile)))


def calculate_earnings(
    *,
    available_minutes: int,
    active_minutes: int,
    waiting_minutes: int,
    miles: object = 0,
    tips: object = 0,
    deductions: object = 0,
    num_orders: int = 1,
    config: EarningsConfig | None = None,
) -> EarningsResult:
    cfg = config or EarningsConfig()
    miles_d = Decimal(str(miles))

    active_payout = _money(Decimal(max(0, active_minutes)) * cfg.per_active_minute)
    waiting_time_payout = _money(Decimal(max(0, waiting_minutes)) * cfg.per_waiting_minute)
    mileage = mileage_payout(miles_d, cfg.per_mile)
    order_bonus = _money(Decimal(max(0, num_orders)) * cfg.per_order_bonus)

    base = _money(active_payout + waiting_time_payout + mileage + order_bonus)
    floor_guarantee = floor_pay(available_minutes, cfg.floor_per_hour)
    floor_topup = _money(max(Decimal("0"), floor_guarantee - base))

    tips_d = _money(tips)
    deductions_d = _money(deductions)
    gross = _money(base + floor_topup + tips_d)
    net = _money(gross - deductions_d)

    return EarningsResult(
        available_minutes=available_minutes,
        active_minutes=active_minutes,
        waiting_minutes=waiting_minutes,
        miles=_money(miles_d),
        num_orders=num_orders,
        active_payout=active_payout,
        waiting_time_payout=waiting_time_payout,
        mileage_payout=mileage,
        order_bonus=order_bonus,
        floor_guarantee=floor_guarantee,
        floor_topup=floor_topup,
        tips=tips_d,
        gross_earnings=gross,
        deductions=deductions_d,
        net_earnings=net,
    )
