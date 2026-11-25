"""R43: menu editing rules (prices, the >50% confirmation, schedules, the history's diff)."""
from datetime import datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from core_api.modules.catalog.service import menu_edit as edit


@pytest.mark.parametrize(("price", "currency", "ok"), [
    ("12.99", "USD", True), ("0.01", "USD", True), ("12.999", "USD", False), ("0", "USD", False), ("-1", "USD", False),
    ("120", "INR", True), ("120.00", "INR", True), ("120.50", "INR", False), ("0", "INR", False),
])
def test_price_rules(price: str, currency: str, ok: bool) -> None:
    assert (edit.price_problem(Decimal(price), currency) is None) is ok


def test_an_option_may_cost_nothing_but_not_less() -> None:
    assert edit.price_problem(Decimal("0"), "INR", allow_zero=True) is None
    assert edit.price_problem(Decimal("-5"), "INR", allow_zero=True)
    assert "whole" in (edit.price_problem(Decimal("10.5"), "INR", allow_zero=True) or "")


@pytest.mark.parametrize(("old", "new", "big"), [
    ("10", "15", False), ("10", "15.01", True), ("10", "5", False), ("10", "4.99", True), ("0", "10", False),
])
def test_more_than_half_needs_a_confirmation(old: str, new: str, big: bool) -> None:
    assert edit.big_change(Decimal(old), Decimal(new)) is big
    if big:
        with pytest.raises(edit.RuleError) as e:
            edit.confirm_needed(Decimal(old), Decimal(new), False)
        assert e.value.code == "PRICE_CONFIRM" and e.value.details["old"] == f"{Decimal(old):.2f}"
        edit.confirm_needed(Decimal(old), Decimal(new), True)  # confirmed: fine


def test_windows_and_past_midnight() -> None:
    assert edit.in_window(time(7), time(11), time(7)) and edit.in_window(time(7), time(11), time(10, 59))
    assert not edit.in_window(time(7), time(11), time(11)) and not edit.in_window(time(7), time(11), time(6, 59))
    assert edit.in_window(time(22), time(2), time(23)) and edit.in_window(time(22), time(2), time(1))
    assert not edit.in_window(time(22), time(2), time(12))
    assert edit.in_window(None, None, time(3))
    for start, end in ((time(7), None), (None, time(7)), (time(7), time(7))):
        with pytest.raises(edit.RuleError):
            edit.check_window(start, end)


def test_a_dish_follows_its_own_and_its_categorys_schedule() -> None:
    dish = SimpleNamespace(available_from=None, available_until=None)
    breakfast = SimpleNamespace(available_from=time(7), available_until=time(11))
    at = lambda h: datetime(2026, 11, 25, h, 0)  # noqa: E731
    assert edit.served_now(dish, breakfast, at(8)) and not edit.served_now(dish, breakfast, at(12))  # type: ignore[arg-type]
    assert edit.schedule_of(dish, breakfast) == {"from": "07:00", "until": "11:00"}  # type: ignore[arg-type]
    own = SimpleNamespace(available_from=time(9), available_until=time(10))
    assert not edit.served_now(own, breakfast, at(8))  # type: ignore[arg-type]
    assert edit.schedule_of(own, breakfast) == {"from": "09:00", "until": "10:00"}  # type: ignore[arg-type]


def test_seconds_to_the_next_schedule_edge() -> None:
    local = datetime(2026, 11, 25, 10, 30)
    assert edit.seconds_to_next_edge([(time(7), time(11))], local) == 30 * 60
    assert edit.seconds_to_next_edge([(time(7), time(9))], local) == 20.5 * 3600  # tomorrow 07:00
    assert edit.seconds_to_next_edge([], local) is None


def test_diff_names_old_and_new() -> None:
    assert edit.diff({"name": "Dosa", "price": "80.00"}, {"name": "Masala Dosa", "price": "80.00"}) == [
        {"field": "name", "old": "Dosa", "new": "Masala Dosa"}]
    assert edit.snapshot(SimpleNamespace(price=Decimal("12.5"), available_from=time(7)), ("price", "available_from")) == {
        "price": "12.50", "available_from": "07:00"}
