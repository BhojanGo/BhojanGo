"""Unit tests for the driver earnings calculation module."""
from decimal import Decimal

from app.services.earnings import (
    EarningsConfig,
    calculate_earnings,
    floor_pay,
    mileage_payout,
)


def test_floor_pay():
    assert floor_pay(120, Decimal("12.00")) == Decimal("24.00")
    assert floor_pay(0, Decimal("12.00")) == Decimal("0.00")
    assert floor_pay(90, Decimal("12.00")) == Decimal("18.00")


def test_mileage_payout():
    assert mileage_payout(10, Decimal("0.65")) == Decimal("6.50")
    assert mileage_payout("2.5", Decimal("0.65")) == Decimal("1.63")  # 1.625 -> 1.63


FLOOR_30 = EarningsConfig(floor_per_hour=Decimal("30.00"))


def test_floor_counts_engaged_time_only():
    # Online 2 h, engaged 1 h (45 min driving to the restaurant and on to the
    # customer, 15 min waiting at the restaurant): the floor covers the hour.
    r = calculate_earnings(available_minutes=120, active_minutes=45, waiting_minutes=15, miles=0, num_orders=0,
                           config=FLOOR_30)
    assert r.engaged_minutes == 60
    assert r.active_payout == Decimal("11.25") and r.waiting_time_payout == Decimal("2.25")
    assert r.floor_guarantee == Decimal("30.00")
    assert r.floor_topup == Decimal("16.50")  # 30.00 - 13.50
    assert r.gross_earnings == Decimal("30.00")


def test_online_without_an_order_has_no_floor():
    r = calculate_earnings(available_minutes=120, active_minutes=0, waiting_minutes=0, miles=0, num_orders=0,
                           config=FLOOR_30)
    assert r.floor_guarantee == Decimal("0.00") and r.gross_earnings == Decimal("0.00")


def test_no_topup_when_base_exceeds_floor():
    r = calculate_earnings(
        available_minutes=60, active_minutes=200, waiting_minutes=0, miles=10,
        tips="5.00", deductions="2.00", num_orders=3,
    )
    # base = 50.00 + 0 + 6.50 + 4.50 = 61.00 > floor 40.00 (200 engaged min x 12/h)
    assert r.floor_topup == Decimal("0.00")
    assert r.gross_earnings == Decimal("66.00")   # 61.00 + 5.00 tips
    assert r.net_earnings == Decimal("64.00")     # - 2.00 deductions


def test_tips_excluded_from_floor():
    # base 5.00 (20 engaged min), floor 10.00 -> topup 5.00; tips on top
    r = calculate_earnings(
        available_minutes=60, active_minutes=20, waiting_minutes=0, miles=0,
        tips="20.00", num_orders=0, config=FLOOR_30,
    )
    assert r.floor_topup == Decimal("5.00")
    assert r.gross_earnings == Decimal("30.00")   # 5 + 5 + 20


def test_batch_complexity_increases_pay():
    one = calculate_earnings(available_minutes=30, active_minutes=60, waiting_minutes=0, miles=5, num_orders=1)
    three = calculate_earnings(available_minutes=30, active_minutes=60, waiting_minutes=0, miles=5, num_orders=3)
    assert three.order_bonus > one.order_bonus
    assert three.gross_earnings > one.gross_earnings


def test_custom_config():
    cfg = EarningsConfig(floor_per_hour=Decimal("18.00"), per_mile=Decimal("1.00"), per_active_minute=Decimal("0"))
    r = calculate_earnings(available_minutes=90, active_minutes=60, waiting_minutes=0, miles=0, num_orders=0, config=cfg)
    assert r.floor_guarantee == Decimal("18.00")
    assert r.gross_earnings == Decimal("18.00")


def test_all_required_fields_present():
    r = calculate_earnings(available_minutes=60, active_minutes=30, waiting_minutes=10, miles=4, tips="3", deductions="1", num_orders=2)
    d = r.to_dict()
    for key in ("gross_earnings", "mileage_payout", "waiting_time_payout", "tips", "deductions", "net_earnings"):
        assert key in d


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all earnings tests passed")
