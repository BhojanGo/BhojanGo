"""Delivery PINs (R27): random 4 digits for every order in every environment, never a
fixed or weak code; the customer sees it only once the rider has picked the order up."""
import re
from collections import Counter

import pytest

from core_api.modules.orders.service import pin as pin_svc
from core_api.modules.orders.service.pin import delivery_pin, is_weak, visible_to_customer

FOUR_DIGITS = re.compile(r"^\d{4}$")


def test_pins_are_random_four_digits_and_never_constant() -> None:
    pins = [delivery_pin() for _ in range(2000)]
    assert all(FOUR_DIGITS.match(p) for p in pins)
    assert len(set(pins)) > 1500  # ~1820 distinct expected out of ~9970 codes; a constant gives 1
    assert Counter(pins).most_common(1)[0][1] < 10
    assert "1234" not in pins and "0000" not in pins


@pytest.mark.parametrize("weak", ["0000", "1111", "9999", "1234", "0123", "6789", "7890", "9012", "4321", "9876", "3210", "0987"])
def test_weak_codes_are_recognised(weak: str) -> None:
    assert is_weak(weak)


@pytest.mark.parametrize("ok", ["4821", "1235", "1243", "2580", "1122", "0102"])
def test_ordinary_codes_are_not_weak(ok: str) -> None:
    assert not is_weak(ok)


def test_a_weak_draw_is_drawn_again(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    draws = iter([1234, 0, 7777, 4821])
    monkeypatch.setattr(pin_svc.secrets, "randbelow", lambda n: next(draws))
    assert delivery_pin() == "4821"


def test_no_fixed_pin_setting_left() -> None:
    from shared.config import get_settings

    p = get_settings().providers
    assert not hasattr(p, "DELIVERY_PIN_FIXED") and not hasattr(p, "DELIVERY_PIN_FIXED_PHONE_PREFIXES")


@pytest.mark.parametrize(("status", "shown"), [
    ("pending_payment", False), ("placed", False), ("accepted", False), ("preparing", False),
    ("almost_ready", False), ("ready", False), ("picked_up", True), ("delivered", False), ("cancelled", False)])
def test_customer_sees_the_pin_only_after_pickup(status: str, shown: bool) -> None:
    assert visible_to_customer(status) is shown
