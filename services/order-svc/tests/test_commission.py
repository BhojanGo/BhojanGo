"""Unit tests for the restaurant-friendly commission model."""
from decimal import Decimal

from app.services.commission import platform_revenue, restaurant_payout


def test_percentage_commission():
    # 20% of 100.00 = 20.00
    assert platform_revenue("percentage_commission", "100.00", commission_rate="0.20") == Decimal("20.00")


def test_percentage_commission_rounds_half_up():
    # 18% of 49.95 = 8.991 -> 8.99
    assert platform_revenue("percentage_commission", "49.95", commission_rate="0.18") == Decimal("8.99")


def test_flat_fee_per_order():
    assert platform_revenue("flat_fee_per_order", "100.00", flat_fee_per_order="6.00") == Decimal("6.00")
    # flat fee ignores subtotal
    assert platform_revenue("flat_fee_per_order", "5.00", flat_fee_per_order="6.00") == Decimal("6.00")


def test_monthly_subscription_zero_per_order():
    assert platform_revenue("monthly_subscription", "250.00", monthly_subscription_fee="999.00") == Decimal("0.00")


def test_unknown_model_defaults_to_commission():
    assert platform_revenue("???", "100.00", commission_rate="0.10") == Decimal("10.00")


def test_restaurant_payout():
    fee = platform_revenue("percentage_commission", "100.00", commission_rate="0.20")
    assert restaurant_payout("100.00", fee) == Decimal("80.00")


def test_restaurant_payout_flat_fee():
    fee = platform_revenue("flat_fee_per_order", "30.00", flat_fee_per_order="5.00")
    assert restaurant_payout("30.00", fee) == Decimal("25.00")


def test_return_type_is_decimal():
    assert isinstance(platform_revenue("percentage_commission", "10", commission_rate="0.2"), Decimal)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all commission tests passed")
