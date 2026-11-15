"""A city's prices for the website (markets city page) and the checkout tip buttons."""
from decimal import Decimal

from core_api.modules.pricing.service.summary import summarize, tip_presets
from core_api.modules.pricing.tests.test_engine import rule


def resolved(*rules):  # type: ignore[no-untyped-def]
    return {r.slot: r for r in rules}


def test_city_pricing_from_rules() -> None:
    out = summarize(resolved(
        rule("delivery_fee", "distance_slabs", {"slabs": [{"up_to": 3, "fee": 25}, {"up_to": 6, "fee": 35}]}),
        rule("customer_fee", "service_fee", {"percent": 2, "min": 5, "max": 15}),
        rule("customer_fee", "small_order_fee", {"below": 99, "fee": 15}),
        rule("business", "max_radius", {"distance": 10}),
        rule("business", "tip_presets", {"amounts": [10, 20, 30], "default_index": 1}),
    ), currency="INR", distance_unit="km", zone_minimums=[("Madhapur", Decimal("149")), ("Kondapur", None)])
    assert out.delivery_fee is not None and out.delivery_fee.type == "distance_slabs"
    assert [(s.up_to, s.fee) for s in out.delivery_fee.slabs] == [(Decimal(3), Decimal(25)), (Decimal(6), Decimal(35))]
    assert out.delivery_from == Decimal(25)
    assert out.service_fee and (out.service_fee.percent, out.service_fee.min, out.service_fee.max) == (2, 5, 15)
    assert out.small_order_fee and (out.small_order_fee.below, out.small_order_fee.fee) == (99, 15)
    assert [(m.zone, m.min_order) for m in out.min_order] == [("Madhapur", Decimal(149))]
    assert out.max_distance == 10
    assert out.tip_presets and out.tip_presets.amounts == [10, 20, 30] and out.tip_presets.default_index == 1
    assert (out.currency, out.distance_unit) == ("INR", "km")


def test_no_rules_means_nulls() -> None:
    out = summarize({}, currency="USD", distance_unit="mi", zone_minimums=[])
    assert out.delivery_fee is None and out.delivery_from is None and out.service_fee is None
    assert out.small_order_fee is None and out.tip_presets is None and out.min_order == []


def test_other_delivery_templates() -> None:
    flat = summarize(resolved(rule("delivery_fee", "flat", {"amount": "2.99"})), currency="USD", distance_unit="mi",
                     zone_minimums=[])
    assert flat.delivery_fee and flat.delivery_fee.amount == Decimal("2.99") and flat.delivery_from == Decimal("2.99")
    free = summarize(resolved(rule("delivery_fee", "free_above", {"min_subtotal": 300, "otherwise": 30})),
                     currency="INR", distance_unit="km", zone_minimums=[])
    assert free.delivery_fee and free.delivery_fee.min_subtotal == 300 and free.delivery_from == 30


def test_tip_presets_without_a_default() -> None:
    p = tip_presets(resolved(rule("business", "tip_presets", {"amounts": [2, 3, 5]})))
    assert p is not None and p.amounts == [2, 3, 5] and p.default_index is None
    assert tip_presets({}) is None
