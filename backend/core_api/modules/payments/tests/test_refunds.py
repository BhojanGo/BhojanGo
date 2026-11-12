"""Refund by item: price minus its discount share, plus its matching tax (P12)."""
from dataclasses import asdict
from decimal import Decimal

import pytest

from core_api.modules.payments.service.refunds import ItemRequest, RefundError, compute_item_refund, limited_to_agent
from core_api.modules.pricing.tests.test_engine import quote
from shared.authz import Assignment

ITEMS = [
    {"menu_item_id": "biryani", "name": "Chicken Dum Biryani", "quantity": 1, "unit_price": "340.00"},
    {"menu_item_id": "tikka", "name": "Paneer Tikka", "quantity": 1, "unit_price": "220.00"},
]


@pytest.fixture
def bill() -> list[dict]:
    """The Hyderabad worked example's bill (₹638.22), as stored in the snapshot."""
    return [{**asdict(ln), "amount": str(ln.amount)} for ln in quote().lines]


def test_one_item_with_its_discount_share_and_gst(bill) -> None:
    total, lines = compute_item_refund(ITEMS, bill, [ItemRequest("tikka", 1)], {}, False, False)
    [line] = lines
    # 220 food, -19.64 of the ₹50 discount (220/560), GST 5% on food: 26.00 x 200.36/520 = 10.02
    assert (line["food"], line["discount"], line["tax"]) == ("220.00", "-19.64", "10.02")
    assert total == Decimal("210.38")


def test_whole_food_matches_the_bill(bill) -> None:
    total, _ = compute_item_refund(ITEMS, bill, [ItemRequest("biryani", 1), ItemRequest("tikka", 1)], {}, False, False)
    # 510 after the discount, plus its share of the ₹26 GST (whose base 520 includes ₹10 packaging): 25.50
    assert total == Decimal("535.50")


def test_delivery_fee_with_its_gst(bill) -> None:
    total, lines = compute_item_refund(ITEMS, bill, [], {}, True, False)
    # 35 + 18% GST share: 11.02 x 35/61.20 = 6.30
    assert lines[0]["fee"] == "35.00" and lines[0]["tax"] == "6.30" and total == Decimal("41.30")
    with pytest.raises(RefundError):
        compute_item_refund(ITEMS, bill, [], {}, True, True)  # already refunded


def test_cannot_refund_more_than_was_ordered(bill) -> None:
    with pytest.raises(RefundError):
        compute_item_refund(ITEMS, bill, [ItemRequest("tikka", 2)], {}, False, False)
    with pytest.raises(RefundError):
        compute_item_refund(ITEMS, bill, [ItemRequest("tikka", 1)], {"tikka": 1}, False, False)
    with pytest.raises(RefundError):
        compute_item_refund(ITEMS, bill, [ItemRequest("naan", 1)], {}, False, False)


def test_us_sales_tax_share() -> None:
    bill = [
        {"code": "food", "amount": "25.00", "taxable_as": "food"},
        {"code": "delivery_fee", "amount": "1.99", "taxable_as": "delivery_fee"},
        {"code": "tax", "amount": "1.69", "detail": {"base": "28.24", "targets": "delivery_fee,food,service_fee"}},
    ]
    items = [{"menu_item_id": "bowl", "name": "Bowl", "quantity": 2, "unit_price": "12.50"}]
    total, lines = compute_item_refund(items, bill, [ItemRequest("bowl", 1)], {}, False, False)
    assert lines[0]["tax"] == "0.75" and total == Decimal("13.25")  # 1.69 x 12.50/28.24 = 0.748


@pytest.mark.parametrize(("roles", "limited"), [
    ([Assignment("support_agent", "IN-TG-HYD")], True),
    ([Assignment("support_agent", "IN-TG-HYD"), Assignment("finance", "IN")], False),
    ([Assignment("city_ops", "IN-TG-HYD")], False),
    ([Assignment("super_admin", "*")], False),
])
def test_who_is_limited(roles, limited) -> None:
    assert limited_to_agent(roles, "IN-TG-HYD") is limited
