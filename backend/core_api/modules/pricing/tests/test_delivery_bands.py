"""R31: the delivery fee from distance bands (road distance), 100% to the delivery partner; the max delivery
distance; the BhojanGo wallet without a payment fee; GST per bill line in India; road distance from OSRM with a
logged straight-line fallback."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from core_api.modules.pricing.service import fees
from core_api.modules.pricing.service.engine import CartLine, ExternalTax, NotDeliverable, QuoteInputs, compute
from core_api.modules.pricing.tests.test_fee_model_v2 import NOW, rule
from core_api.modules.rules.service.resolver import Context, resolve

US_BANDS = {"slabs": [{"up_to": 2, "fee": "3.50"}, {"up_to": 4, "fee": "4.50"}, {"up_to": 6, "fee": "5.50"},
                      {"up_to": 8, "fee": "6.50"}]}
IN_BANDS = {"slabs": [{"up_to": 3, "fee": 30}, {"up_to": 5, "fee": 40}, {"up_to": 7, "fee": 50}]}
BOISE_AT = datetime(2026, 11, 23, 12, 0, tzinfo=ZoneInfo("America/Boise"))
HYD_AT = datetime(2026, 11, 23, 13, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def us() -> dict:
    rs = [rule("delivery_fee", "distance_slabs", US_BANDS, "city", "US-ID-BOI"),
          rule("business", "max_radius", {"distance": 8}),
          rule("fee", "platform_fee_pct", {"percent": 10}), rule("fee", "min_platform_fee", {"amount": "0.99"}),
          rule("commission", "percent", {"percent": 0}),
          rule("fee", "card_fee_estimate", {"card": {"percent": "2.9", "fixed": "0.30"}}),
          rule("tax", "external", {"provider": "stripe_tax"})]
    return {r.slot: r for r in rs}


def india() -> dict:
    rs = [rule("delivery_fee", "distance_slabs", IN_BANDS, "city", "IN-TG-HYD"),
          rule("business", "max_radius", {"distance": 7}, scope_id="IN"),
          rule("fee", "platform_fee_pct", {"percent": 10}, scope_id="IN"), rule("fee", "min_platform_fee", {"amount": 15}, scope_id="IN"),
          rule("commission", "percent", {"percent": 0}, scope_id="IN"),
          rule("fee", "card_fee_estimate", {"card": {"percent": 2}, "upi": {"percent": 0}, "wallet": {"percent": 2},
                                            "net_banking": {"percent": 2}}, scope_id="IN"),
          # India's seeded GST rules, unchanged (tools/seed/data.py)
          rule("tax", "rate_on_lines", {"label": "GST on food", "rate_percent": 5, "target_lines": ["food", "packaging"],
                                         "collected_by": "platform", "platform_discounts_reduce_base": False}, scope_id="IN"),
          rule("tax", "rate_on_lines", {"label": "GST on platform fees", "rate_percent": 18,
                                         "target_lines": ["delivery_fee", "platform_fee", "service_fee", "surge",
                                                          "small_order_fee", "late_night_fee"],
                                         "collected_by": "platform", "platform_discounts_reduce_base": False}, scope_id="IN")]
    out = {}
    for r in rs:  # the two GST rules are keyed slots
        out[r.slot if r.family != "tax" else f"tax:{r.params['label']}"] = r
    return out


def delivery(rules: dict, distance: str, currency: str, at: datetime) -> Decimal:
    q = compute(QuoteInputs(currency=currency, lines=[CartLine("Dish", 1, Decimal("20"))], distance=Decimal(distance),
                            local_time=at), rules)
    return next(ln.amount for ln in q.lines if ln.code == "delivery_fee")


def test_boise_bands_and_max_distance() -> None:
    assert delivery(us(), "2.00", "USD", BOISE_AT) == Decimal("3.50")  # 0-2 includes 2.00
    assert delivery(us(), "3.00", "USD", BOISE_AT) == Decimal("4.50")
    assert delivery(us(), "8.00", "USD", BOISE_AT) == Decimal("6.50")
    with pytest.raises(NotDeliverable):
        delivery(us(), "8.50", "USD", BOISE_AT)


def test_hyderabad_bands_in_whole_rupees_and_max_distance() -> None:
    assert delivery(india(), "2.50", "INR", HYD_AT) == Decimal("30")
    assert delivery(india(), "4.20", "INR", HYD_AT) == Decimal("40")
    with pytest.raises(NotDeliverable):
        delivery(india(), "7.39", "INR", HYD_AT)


def test_bands_alone_also_stop_at_their_last_band() -> None:
    """Without a max distance rule, the last band is the limit (no per-unit beyond it)."""
    rules = {k: v for k, v in us().items() if k != "business:max_radius"}
    with pytest.raises(NotDeliverable):
        delivery(rules, "8.01", "USD", BOISE_AT)


def test_boise_full_order() -> None:
    inp = QuoteInputs(currency="USD", lines=[CartLine("A", 1, Decimal("3.99")), CartLine("B", 1, Decimal("10.99")),
                                            CartLine("C", 1, Decimal("22.00"))], distance=Decimal("3.00"), local_time=BOISE_AT)
    # R33: Idaho's taxable lines (food + platform fee; the delivery fee is untaxed), through the tax provider
    from core_api.modules.pricing.tests.test_idaho_tax import idaho, taxed

    q = taxed(inp, idaho(us()))
    line = {ln.code: ln.amount for ln in q.lines}
    assert (line["platform_fee"], line["delivery_fee"], line["tax"]) == (Decimal("3.70"), Decimal("4.50"), Decimal("2.44"))
    assert q.total == Decimal("47.62")
    assert q.split.card_fee == Decimal("1.68")  # 2.9% of 47.62 + 0.30 = 1.6810
    assert q.split.restaurant == Decimal("35.30")
    assert q.split.rider == Decimal("4.50") == q.split.detail["delivery_fee_to_partner"]  # never more, never less
    assert q.split.platform == Decimal("3.70")
    assert q.split.restaurant + q.split.rider + q.split.tax + q.split.platform + q.split.card_fee == q.total


def hyderabad(method: str):  # type: ignore[no-untyped-def]
    inp = QuoteInputs(currency="INR", lines=[CartLine("Thali", 1, Decimal("300"))], distance=Decimal("2.50"),
                      local_time=HYD_AT, payment_method=method)
    return compute(inp, india())


def test_hyderabad_upi_order_and_gst_per_line() -> None:
    q = hyderabad("upi")
    line = {ln.label: ln for ln in q.lines}
    assert line["Platform fee"].amount == Decimal("30.00")  # 10% of 300 (above the ₹15 minimum)
    assert line["Delivery fee"].amount == Decimal("30")
    assert q.split.rider == Decimal("30")  # the partner gets the whole delivery fee
    assert q.split.card_fee == Decimal("0")  # UPI: 0%
    assert q.split.restaurant == Decimal("300.00")  # GST is collected by BhojanGo (e-commerce operator), not the restaurant
    # GST, as India's tax rules calculate it today (rates unchanged): 5% on food, 18% on delivery and platform fee
    assert line["GST on food"].amount == Decimal("15.00")
    assert line["GST on food"].detail["by_line"] == "food=15.00"
    assert line["GST on platform fees"].amount == Decimal("10.80")
    assert line["GST on platform fees"].detail["by_line"] == "delivery_fee=5.40;platform_fee=5.40"
    assert q.total == Decimal("385.80")  # 300 + 30 + 30 + 15.00 + 10.80
    assert q.split.tax == Decimal("25.80")


def test_bhojango_wallet_has_no_payment_fee_but_a_gateway_wallet_does() -> None:
    assert hyderabad("wallet").split.card_fee == Decimal("0")  # the BhojanGo wallet: no gateway
    assert hyderabad("wallet").split.restaurant == Decimal("300.00")
    est = india()["fee:card_fee_estimate"].params
    assert fees.method_rate(est, "wallet") is None
    assert Decimal(fees.method_rate(est, "gateway_wallet")["percent"]) == 2  # Paytm etc. inside Razorpay
    assert fees.method_rate(est, fees.GATEWAY_METHOD["wallet"]) == fees.method_rate(est, "gateway_wallet")


def test_restaurant_bands_beat_the_citys() -> None:
    city = rule("delivery_fee", "distance_slabs", US_BANDS, "city", "US-ID-BOI")
    own = rule("delivery_fee", "distance_slabs", {"slabs": [{"up_to": 3, "fee": "1.99"}, {"up_to": 8, "fee": "2.99"}]},
               "restaurant", "r1")
    ctx = Context(country="US", region="US-ID", city="US-ID-BOI", restaurant_id="r1")
    got = resolve([city, own], ctx, NOW)
    assert got["delivery_fee"].scope_level == "restaurant"
    rules = {**us(), "delivery_fee": got["delivery_fee"]}
    assert delivery(rules, "3.00", "USD", BOISE_AT) == Decimal("1.99")
    s = fees.settings(got)["delivery_fee"]
    assert s.value == {"bands": [{"up_to": "3", "fee": "1.99"}, {"up_to": "8", "fee": "2.99"}]} and s.source.level == "restaurant"
    # another restaurant in Boise still gets the city's bands
    other = resolve([city, own], Context(country="US", region="US-ID", city="US-ID-BOI", restaurant_id="r2"), NOW)
    assert other["delivery_fee"].scope_level == "city"


# ── road distance ────────────────────────────────────────────────────────────

def test_osrm_road_distance_and_logged_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from structlog.testing import capture_logs

    from shared.providers import routing

    calls: list[str] = []

    class Resp:
        def __init__(self, body: dict) -> None:
            self.body = body

        def raise_for_status(self) -> None: ...

        def json(self) -> dict:
            return self.body

    def ok(url: str, timeout: float) -> Resp:
        calls.append(url)
        if "/table/" in url:
            return Resp({"code": "Ok", "distances": [[4827.9], [None]], "durations": [[600.0], [None]]})
        return Resp({"code": "Ok", "routes": [{"distance": 4827.9, "duration": 600.0}]})

    monkeypatch.setattr(httpx, "get", ok)
    straight = routing.StraightLineRouting(1.3, 25)
    osrm = routing.OsrmRouting("http://osrm:5000", 1.5, straight)
    a, b = (43.6150, -116.2023), (43.6400, -116.2400)
    assert round(osrm.leg(a, b).distance_km, 4) == 4.8279
    assert calls[0].startswith("http://osrm:5000/route/v1/driving/-116.2023,43.615;-116.24,43.64")
    with capture_logs() as logs:
        legs = osrm.legs_to([a, (17.4, 78.4)], b)  # the second has no route: estimated, logged
    assert round(legs[0].distance_km, 4) == 4.8279
    assert legs[1].distance_km == straight.leg((17.4, 78.4), b).distance_km
    assert [x["event"] for x in logs] == ["routing_fallback"]

    def down(url: str, timeout: float) -> Resp:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", down)
    with capture_logs() as logs:
        leg = osrm.leg(a, b)
    assert leg.distance_km == pytest.approx(routing.haversine_km(a, b) * 1.3)  # straight line x 1.3
    assert logs[0]["event"] == "routing_fallback" and "ConnectError" in logs[0]["reason"] and logs[0]["road_factor"] == 1.3
