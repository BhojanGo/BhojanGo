"""Delivery PINs: random 4 digits; the fixed test PIN only for seed numbers, never in production."""
import re

import pytest

from core_api.modules.orders.service.pin import delivery_pin
from shared.config import get_settings

FOUR_DIGITS = re.compile(r"^\d{4}$")


@pytest.fixture
def providers(monkeypatch):  # type: ignore[no-untyped-def]
    p = get_settings().providers
    monkeypatch.setattr(p, "DELIVERY_PIN_FIXED", "1234")
    monkeypatch.setattr(p, "DELIVERY_PIN_FIXED_PHONE_PREFIXES", ["+9190000", "+1208555"])
    return p


@pytest.mark.parametrize("phone", ["+919000000101", "+12085550101"])
def test_seed_numbers_get_the_fixed_pin(providers, phone: str) -> None:  # type: ignore[no-untyped-def]
    assert delivery_pin(phone) == "1234"


@pytest.mark.parametrize("phone", ["+919876543210", "+14155550123", "+12085560101", None])
def test_real_numbers_get_random_pins(providers, phone: str | None) -> None:  # type: ignore[no-untyped-def]
    pins = [delivery_pin(phone) for _ in range(40)]
    assert all(FOUR_DIGITS.match(p) for p in pins)
    assert len(set(pins)) > 1  # random, not one value (all 40 equal: 1 in 10^156)
    assert pins.count("1234") < 40


def test_no_fixed_pin_when_switched_off(providers, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(providers, "DELIVERY_PIN_FIXED", "")
    assert len({delivery_pin("+919000000101") for _ in range(40)}) > 1


def test_no_fixed_pin_in_an_environment_named_production(providers, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert len({delivery_pin("+919000000101") for _ in range(40)}) > 1
