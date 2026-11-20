"""R22 security review (S12): a bulk refund runs without a second admin only when every
order is within the city's per-order limit AND the batch is within its total limit.
Before, 500 orders each just under the limit ran at once.

Imports are inside the tests so the file still collects with the fix reverted (each
test then fails, which is how the fix was proven)."""
from decimal import Decimal


def test_many_small_orders_over_the_total_need_a_second_admin() -> None:
    from core_api.modules.incidents.service import approval_reasons

    # ₹100 per order, ₹5,000 for the batch: 500 orders of ₹99 each is ₹49,500
    assert approval_reasons([9900] * 500, Decimal(100), Decimal(5000)) == ["total_over_limit"]


def test_within_both_limits_runs_at_once() -> None:
    from core_api.modules.incidents.service import approval_reasons

    assert approval_reasons([9900] * 50, Decimal(100), Decimal(5000)) == []
    assert approval_reasons([], Decimal(0), Decimal(0)) == []


def test_one_big_order_still_needs_a_second_admin() -> None:
    from core_api.modules.incidents.service import approval_reasons

    assert approval_reasons([10001], Decimal(100), Decimal(5000)) == ["order_over_limit"]
    assert approval_reasons([10001] * 100, Decimal(100), Decimal(5000)) == ["order_over_limit", "total_over_limit"]


def test_the_rule_takes_an_optional_total() -> None:
    from core_api.modules.rules.service.templates import AutoRefundLimit

    assert AutoRefundLimit(max_per_order=Decimal(100), max_bulk_total=Decimal(2000)).max_bulk_total == Decimal(2000)
    assert AutoRefundLimit(max_per_order=Decimal(100)).max_bulk_total is None


def test_the_default_total_is_fifty_orders() -> None:
    from core_api.modules.incidents import service

    assert service.AUTO_TOTAL_TIMES == Decimal(50)
