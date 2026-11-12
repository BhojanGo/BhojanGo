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
