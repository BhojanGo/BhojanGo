"""R32: pickup orders (no delivery fee, no delivery partner, no distance limit; their own platform fee, 5% of
food with the same minimum), India's "platform-funded offers reduce GST base" setting, and road-vs-fallback
routing monitoring."""
from dataclasses import replace
from decimal import Decimal

from core_api.modules.orders.service import state_machine as sm
from core_api.modules.pricing.service import fees
from core_api.modules.pricing.service import routing_stats as rs
from core_api.modules.pricing.service.engine import CartLine, ExternalTax, QuoteInputs, compute
from core_api.modules.pricing.tests.test_delivery_bands import BOISE_AT, HYD_AT, india, us
from core_api.modules.pricing.tests.test_fee_model_v2 import BOISE, NOW, rule
from core_api.modules.rules.service.resolver import Context, resolve
from core_api.modules.rules.service.templates import allowed_levels
from shared.providers.routing import OsrmRouting, StraightLineRouting


def us_pickup() -> dict:
    return {**us(), "fee:pickup_platform_fee_pct": rule("fee", "pickup_platform_fee_pct", {"percent": 5})}


def india_pickup() -> dict:
    return {**india(), "fee:pickup_platform_fee_pct": rule("fee", "pickup_platform_fee_pct", {"percent": 5}, scope_id="IN")}


def test_boise_pickup_card() -> None:
    """3.99 + 10.99 + 22.00, Idaho 6%, card: platform 1.85, tax 2.33, total 41.16, card fee 1.49 (the
    restaurant's), restaurant 35.49, no delivery partner payout. Far beyond the 8 mi max: pickup has no limit.
    R33: the tax comes from Idaho's taxable lines (food + platform fee), not a food-only figure fed in."""
    from core_api.modules.pricing.tests.test_idaho_tax import idaho, taxed

    inp = QuoteInputs(currency="USD", lines=[CartLine("A", 1, Decimal("3.99")), CartLine("B", 1, Decimal("10.99")),
                                            CartLine("C", 1, Decimal("22.00"))], distance=Decimal("0"),
                      local_time=BOISE_AT, fulfillment="pickup")
    q = taxed(inp, idaho(us_pickup()))
    inp = replace(inp, external_tax=[ExternalTax(ln.label, Decimal(ln.detail["rate_percent"]), Decimal(ln.detail["base"]),
                                                 ln.amount, "US-ID", "local", "taxcalc_test")
                                     for ln in q.lines if ln.code == "tax"])
    line = {ln.code: ln.amount for ln in q.lines}
    assert "delivery_fee" not in line and "tip" not in line
    assert (line["platform_fee"], line["tax"]) == (Decimal("1.85"), Decimal("2.33"))  # 5% of 36.98 = 1.849; 6% of 38.83
    assert q.total == Decimal("41.16")
    assert q.split.card_fee == Decimal("1.49")  # 2.9% of 41.16 + 0.30 = 1.4936
    assert q.split.restaurant == Decimal("35.49")  # 36.98 - 1.49
    assert q.split.rider == Decimal("0")
    assert q.split.platform == Decimal("1.85")
    assert q.split.restaurant + q.split.rider + q.split.tax + q.split.platform + q.split.card_fee == q.total
    far = compute(replace(inp, distance=Decimal("40")), us_pickup())  # no max distance for pickup
    assert far.total == q.total


def test_hyderabad_pickup_upi() -> None:
    """₹300 food, UPI: platform ₹15 (5% = 15, the minimum), GST food 15.00 + platform 2.70, total 332.70,
    restaurant 300."""
    q = compute(QuoteInputs(currency="INR", lines=[CartLine("Thali", 1, Decimal("300"))], distance=Decimal("0"),
                            local_time=HYD_AT, payment_method="upi", fulfillment="pickup"), india_pickup())
    line = {ln.label: ln for ln in q.lines}
    assert "Delivery fee" not in line
    assert line["Platform fee"].amount == Decimal("15.00")
    assert line["GST on food"].amount == Decimal("15.00")
    assert line["GST on platform fees"].amount == Decimal("2.70")
    assert line["GST on platform fees"].detail["by_line"] == "platform_fee=2.70"
    assert q.total == Decimal("332.70")
    assert q.split.restaurant == Decimal("300.00")
    assert q.split.rider == Decimal("0") and q.split.card_fee == Decimal("0")


def test_pickup_minimum_and_fallback_to_the_delivery_platform_fee() -> None:
    small = QuoteInputs(currency="INR", lines=[CartLine("Chai", 1, Decimal("100"))], distance=Decimal("0"),
                        local_time=HYD_AT, payment_method="upi", fulfillment="pickup")
    assert {ln.code: ln.amount for ln in compute(small, india_pickup()).lines}["platform_fee"] == Decimal("15.00")
    # no pickup rule at all: the delivery platform fee (10%) applies
    assert {ln.code: ln.amount for ln in compute(replace(small, lines=[CartLine("T", 1, Decimal("300"))]),
                                                  india()).lines}["platform_fee"] == Decimal("30.00")


def test_delivery_is_unchanged_by_the_pickup_fee() -> None:
    q = compute(QuoteInputs(currency="INR", lines=[CartLine("Thali", 1, Decimal("300"))], distance=Decimal("2.50"),
                            local_time=HYD_AT, payment_method="upi"), india_pickup())
    assert {ln.code: ln.amount for ln in q.lines}["platform_fee"] == Decimal("30.00")
    assert q.total == Decimal("385.80")  # R31's Hyderabad order, to the paisa


def _offer_order(setting: bool | None):  # type: ignore[no-untyped-def]
    rules = india_pickup()
    offer = rule("promotion", "percent_off", {"percent": 10, "max_discount": 100, "funded_by": "platform"}, scope_id="IN")
    rules[offer.slot] = offer
    if setting is not None:
        rules["business:gst_offer_base"] = rule("business", "gst_offer_base", {"platform_offers_reduce_base": setting},
                                                scope_id="IN")
    q = compute(QuoteInputs(currency="INR", lines=[CartLine("Biryani", 1, Decimal("480"))], distance=Decimal("2.50"),
                            local_time=HYD_AT, payment_method="upi"), rules)
    line = {ln.label: ln for ln in q.lines}
    assert next(ln for ln in q.lines if ln.code == "promotion").amount == Decimal("-48.00")
    return line["GST on food"].amount, q


def test_gst_on_platform_funded_offers() -> None:
    """₹480 food, ₹48 BhojanGo offer: OFF (default) GST on food ₹24.00; ON ₹21.60."""
    assert _offer_order(False)[0] == Decimal("24.00")
    assert _offer_order(None)[0] == Decimal("24.00")  # no setting: India's tax rules (don't reduce) as before
    on, q = _offer_order(True)
    assert on == Decimal("21.60")
    assert any("gst_offer_base" in str(u) for u in q.rules_used)


def test_pickup_fee_settings_at_four_levels_and_gst_at_country_only() -> None:
    assert allowed_levels("fee", "pickup_platform_fee_pct") >= {"country", "region", "city", "restaurant"}
    assert allowed_levels("business", "gst_offer_base") == {"country"}
    country = rule("fee", "pickup_platform_fee_pct", {"percent": 5})
    city = rule("fee", "pickup_platform_fee_pct", {"percent": 4}, "city", "US-ID-BOI")
    got = fees.settings(resolve([country, city], BOISE, NOW))["pickup_platform_fee_pct"]
    assert got.value == {"percent": "4"} and got.source.level == "city"
    own = rule("fee", "pickup_platform_fee_pct", {"percent": 3}, "restaurant", "r1")
    ctx = Context(country="US", region="US-ID", city="US-ID-BOI", restaurant_id="r1")
    assert fees.settings(resolve([country, city, own], ctx, NOW))["pickup_platform_fee_pct"].source.level == "restaurant"
    gst = rule("business", "gst_offer_base", {"platform_offers_reduce_base": True}, scope_id="IN")
    assert fees.settings(resolve([gst], Context(country="IN"), NOW))["gst_offer_base"].value == {"on": "true"}


def test_pickup_order_states() -> None:
    assert sm.fits("pickup", "ready", "delivered") and not sm.fits("pickup", "ready", "picked_up")
    assert sm.fits("delivery", "ready", "picked_up") and not sm.fits("delivery", "ready", "delivered")
    assert sm.fits(None, "picked_up", "delivered")
    assert sm.actor_allowed("ready", "delivered", "restaurant") and not sm.actor_allowed("ready", "delivered", "driver")


def test_routing_sources_and_the_fallback_alert_threshold() -> None:
    sl = StraightLineRouting(1.3, 25)
    a, b = (43.6150, -116.2023), (43.6295, -116.2008)
    assert sl.leg(a, b).source == "straight_line"
    down = OsrmRouting("http://127.0.0.1:9", 0.2, sl)  # nothing listens: every leg falls back (logged)
    assert down.leg(a, b).source == "fallback"
    assert down.leg(a, b).distance_km == sl.leg(a, b).distance_km
    assert [x.source for x in down.legs_to([a, a], b)] == ["fallback", "fallback"]
    assert down.health() is False
    assert not rs.over_threshold(1, 19)  # too few to judge
    assert not rs.over_threshold(1, 20)  # exactly 5%
    assert rs.over_threshold(2, 20)  # 10% of 20
    assert rs.fingerprint(BOISE_AT) == "routing-fallback-2026112312"


def test_pickup_has_no_busy_hour_fee() -> None:
    """The busy-hour fee is about delivery demand: a pickup order at 8 pm in Hyderabad still totals ₹332.70."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    rules = india_pickup()
    surge = rule("customer_fee", "surge_levy", {"windows": [{"start": "19:00", "end": "21:30"}], "amount": 15}, scope_id="IN")
    rules[surge.slot] = surge
    at = datetime(2026, 11, 23, 20, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    inp = QuoteInputs(currency="INR", lines=[CartLine("Thali", 1, Decimal("300"))], distance=Decimal("0"),
                      local_time=at, payment_method="upi", fulfillment="pickup")
    assert compute(inp, rules).total == Decimal("332.70")
    delivered = compute(replace(inp, fulfillment="delivery", distance=Decimal("2.50")), rules)
    assert "surge" in {ln.code for ln in delivered.lines}
