"""Payout statements without a database (P13)."""
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from core_api.modules.finance.service.statements import OrderForPayout, active_seconds, restaurant_statement, rider_statement
from core_api.modules.pricing.tests.test_engine import quote

T = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
RIDER_RULE = {"base": "25", "per_unit": "6", "per_wait_minute": "1", "free_wait_minutes": 5}


def worked_example(order_id: str = "o1", start: datetime = T, minutes: int = 30, refunds: list | None = None) -> OrderForPayout:
    q = quote()  # the Hyderabad worked example: ₹638.22
    split = {"restaurant": str(q.split.restaurant), "rider": str(q.split.rider),
             "detail": {k: str(v) for k, v in q.split.detail.items()}}
    return OrderForPayout(
        order_id=order_id, delivered_at=start + timedelta(minutes=minutes), restaurant_id="r1", rider_id="d1",
        lines=[{**asdict(ln), "amount": str(ln.amount)} for ln in q.lines], split=split, distance=Decimal("4.2"),
        rider_rule=RIDER_RULE, started_at=start, refund_lines=refunds or [])


def test_restaurant_statement_matches_the_split() -> None:
    total, summary, lines = restaurant_statement([worked_example()])
    # 560 food + 10 packaging - 84 commission (15%) = 486, as in the spec
    assert total == Decimal("486.00") and lines[0]["net"] == "486.00"
    assert (summary["food"], summary["packaging"], summary["commission"]) == ("560.00", "10.00", "84.00")


def test_commission_gst_and_tds_come_off_the_kitchen() -> None:  # R16
    total, summary, lines = restaurant_statement([worked_example()], Decimal("18"), Decimal("1"))
    # 84 commission x 18% = 15.12 GST; TDS 1% of 570 gross sales (food + packaging) = 5.70
    assert (summary["commission_tax"], summary["tds"]) == ("15.12", "5.70")
    assert lines[0]["commission_tax"] == "-15.12" and lines[0]["tds"] == "-5.70"
    assert total == Decimal("486.00") - Decimal("15.12") - Decimal("5.70")
    assert (summary["commission_tax_percent"], summary["tds_percent"]) == ("18", "1")
    assert restaurant_statement([worked_example()])[0] == Decimal("486.00")  # none set: nothing taken


def test_gst_on_commission_is_rounded_per_order_on_statement_and_invoice_alike() -> None:  # R17
    from core_api.modules.finance.service import commission_invoice as ci

    def small(oid: str) -> OrderForPayout:  # commission 0.25 each: 18% = 0.045 -> 0.05 per order
        return OrderForPayout(order_id=oid, delivered_at=T, restaurant_id="r1", rider_id=None,
                              lines=[{"code": "food", "amount": "2.50"}], split={"detail": {"commission": "0.25"}},
                              distance=Decimal(0), rider_rule=None, started_at=None)

    _, summary, lines = restaurant_statement([small("a"), small("b"), small("c")], Decimal("18"))
    assert [ln["commission_tax"] for ln in lines] == ["-0.05"] * 3 and summary["commission_tax"] == "0.15"
    # one invoice over two statements of the same period adds the per-order amounts, never re-rounds:
    # 0.75 x 18% would be 0.135 -> 0.14; the statements took 0.15, and so does the invoice
    commission, tax, orders = ci.totals([lines[:2], lines[2:]])
    assert (commission, tax, orders) == (Decimal("0.75"), Decimal("0.15"), 3)
    _, worked, wl = restaurant_statement([worked_example()], Decimal("18"))
    assert ci.totals([wl])[1] == Decimal(worked["commission_tax"]) == Decimal("15.12")


def tikka(reason: str, fault: str) -> list[dict]:
    return [{"menu_item_id": "tikka", "name": "Chicken Tikka", "food": "220.00", "quantity": 1,
             "reason": reason, "fault": fault}]


def test_restaurant_fault_refund_comes_off_the_restaurant_less_commission() -> None:
    total, summary, lines = restaurant_statement([worked_example(refunds=tikka("missing_item", "restaurant"))])
    # the restaurant kept 85% of the tikka (15% commission): 220 x 0.85 = 187
    assert summary["refunds"] == "187.00" and total == Decimal("299.00")
    assert lines[0]["refund_details"] == [{"item": "Chicken Tikka", "quantity": 1, "reason": "missing_item",
                                           "fault": "restaurant", "charged_to": "restaurant"}]


def test_delivery_fault_and_goodwill_refunds_are_the_platforms() -> None:
    for reason, fault in (("damaged_in_transit", "delivery"), ("late", "delivery"), ("goodwill", "goodwill")):
        total, summary, lines = restaurant_statement([worked_example(refunds=tikka(reason, fault))])
        assert total == Decimal("486.00") and summary["refunds"] == "0.00"
        # still shown on the statement, so the restaurant sees what happened
        assert lines[0]["refund_details"][0]["reason"] == reason and lines[0]["refund_details"][0]["charged_to"] == "platform"


def test_rider_statement_and_hourly_floor() -> None:
    orders = [worked_example("o1", T, 30), worked_example("o2", T + timedelta(hours=1), 30)]
    total, summary, lines = rider_statement(orders, floor_per_hour=Decimal("120"))
    # each: base 25 + 6 x 4.2 = 25.20 -> 50.20, + tip 20
    assert lines[0]["base"] == "25.00" and lines[0]["distance"] == "25.20" and lines[0]["tip"] == "20.00"
    assert summary["active_hours"] == "1.00"  # two 30 minutes from accepting the offer to drop-off
    # floor: 120 x 1 h = 120 > 100.40 earned -> top-up 19.60 (tips don't count)
    assert summary["floor_top_up"] == "19.60"
    assert total == Decimal("100.40") + Decimal("40.00") + Decimal("19.60")


def test_no_top_up_when_earnings_beat_the_floor() -> None:
    total, summary, _ = rider_statement([worked_example()], floor_per_hour=Decimal("60"))
    assert summary["floor_top_up"] == "0.00" and total == Decimal("70.20")
    total, summary, _ = rider_statement([worked_example()], floor_per_hour=None)
    assert summary["floor_top_up"] == "0.00" and summary["hourly_floor"] is None


def test_waiting_pay_after_free_minutes() -> None:
    o = worked_example()
    o.wait_minutes = Decimal("12")
    _, summary, lines = rider_statement([o], None)
    assert lines[0]["waiting"] == "7.00" and summary["waiting"] == "7.00"


def test_batched_deliveries_count_once() -> None:
    a = (T, T + timedelta(minutes=40))
    b = (T + timedelta(minutes=10), T + timedelta(minutes=50))  # overlaps a
    c = (T + timedelta(hours=2), T + timedelta(hours=2, minutes=15))
    assert active_seconds([a, b, c]) == (50 + 15) * 60
    assert active_seconds([]) == 0


def test_engaged_time_runs_from_accepting_the_offer_to_drop_off() -> None:
    # Accepted at 12:00, drove to the restaurant and waited, picked up 12:20, delivered 12:45:
    # 45 engaged minutes, not the 25 minutes from pickup.
    o = worked_example("o1", T, 45)
    _, summary, _ = rider_statement([o], floor_per_hour=Decimal("120"))
    assert summary["active_hours"] == "0.75"
    # floor 120 x 0.75 = 90 > 50.20 earned -> top-up 39.80
    assert summary["floor_top_up"] == "39.80"



def test_a_later_drop_off_of_a_batch_pays_no_base_but_the_batch_bonus() -> None:
    """Item 2: the second drop-off pays distance + waiting + the city's batch bonus (₹10), no base."""
    from dataclasses import replace

    first = replace(worked_example("o1", T, 40), batch_position=1)
    second = replace(worked_example("o2", T, 40), batch_position=2, batch_bonus=Decimal("10"))
    _, summary, lines = rider_statement([first, second], floor_per_hour=None)
    assert lines[0]["base"] == "25.00" and "batch_bonus" not in lines[0]            # the first drop-off: as usual
    assert lines[1]["base"] == "0.00" and lines[1]["batch_bonus"] == "10.00"       # the second: no base, the bonus
    a, b = lines
    assert (b["distance"], b["waiting"], b["tip"]) == (a["distance"], a["waiting"], a["tip"])  # the rest is unchanged
    assert Decimal(b["total"]) == Decimal(a["total"]) - Decimal(a["base"]) + Decimal("10.00")
    assert summary["base"] == str(Decimal(a["base"]) + Decimal("10.00"))  # the bonus counts as base pay


def test_r29_payout_is_food_less_commission_less_card_fee() -> None:
    """Fee model v2, the B example: food 36.98 - commission 0 - card fee 1.66 = 35.32, shown per order."""
    o = OrderForPayout(order_id="o1", delivered_at=T, restaurant_id="r1", rider_id=None,
                       lines=[{"code": "food", "amount": "36.98"}, {"code": "delivery_fee", "amount": "3.99"},
                              {"code": "platform_fee", "amount": "3.70"}, {"code": "tax", "amount": "2.22"}],
                       split={"restaurant": "35.32", "card_fee": "1.66",
                              "detail": {"commission": "0", "card_fee": "1.66", "delivery_fee_to_partner": "3.99"}},
                       distance=Decimal("1.2"), rider_rule=None, started_at=None)
    total, summary, lines = restaurant_statement([o])
    assert total == Decimal("35.32") and lines[0]["net"] == "35.32"
    assert (lines[0]["food"], lines[0]["commission"], lines[0]["card_fee"]) == ("36.98", "0.00", "-1.66")
    assert summary["card_fee"] == "1.66"
    # Production: the processor's actual fee (on the order) replaces the estimate
    from dataclasses import replace

    assert restaurant_statement([replace(o, card_fee=Decimal("1.60"))])[0] == Decimal("35.38")


def test_r29_partner_gets_the_delivery_fee_when_it_is_more_than_guaranteed_pay() -> None:
    from core_api.modules.finance.service.statements import rider_statement

    def order(fee: str) -> OrderForPayout:
        return OrderForPayout(order_id="o1", delivered_at=T, restaurant_id="r1", rider_id="d1",
                              lines=[], split={"detail": {"tip": "2.00", "delivery_fee_to_partner": fee}},
                              distance=Decimal("1"), rider_rule={"base": "3.00", "per_unit": "1.00"}, started_at=None)
    total, summary, lines = rider_statement([order("4.99")], None)
    assert lines[0]["delivery_fee_extra"] == "0.99" and total == Decimal("6.99")  # 4.99 delivery fee + 2.00 tip
    total, _, lines = rider_statement([order("1.99")], None)
    assert lines[0]["delivery_fee_extra"] == "0.00" and total == Decimal("6.00")  # guaranteed 4.00 + 2.00 tip
