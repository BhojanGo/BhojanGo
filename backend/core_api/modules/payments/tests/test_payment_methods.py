"""Saved cards: what counts as a card number (refused before anything is
stored) and when a card has expired. The API is tested in
identity/tests/test_account.py and core_api/integration/test_account.py."""
from datetime import UTC, datetime

import pytest

from core_api.modules.payments.service.methods import TOKEN_FORMAT, is_expired, looks_like_card_number


@pytest.mark.parametrize("value", [
    "4242424242424242", "4242 4242 4242 4242", "4242-4242-4242-4242", "378282246310005", "6011111111111117",
    "4000 0566 5566 5556", "1234567890123", "1234567890123456789", "pm_4242424242424242", 4242424242424242,
    {"card": {"number": "5555555555554444"}}, ["x", "4111111111111111"], {"4111111111111111": "key"},
])
def test_card_numbers_are_spotted(value: object) -> None:
    assert looks_like_card_number(value)


@pytest.mark.parametrize("value", [
    "4242", "pm_1QaBcDeFgHiJkLmN", "token_4lsdksD31GaZ09", "pm_fake_3f9a2c", "123456789012",  # 12 digits
    "12345678901234567890",  # 20 digits: not a card
    "+14155552671", 2030, 12, True, None, {"exp": "12/30"}, "4242 4242",
])
def test_other_values_pass(value: object) -> None:
    assert not looks_like_card_number(value)


def test_token_formats() -> None:
    assert TOKEN_FORMAT["stripe"].match("pm_1QaBcDeFgHiJkLmN")
    assert not TOKEN_FORMAT["stripe"].match("tok_visa")
    assert TOKEN_FORMAT["razorpay"].match("token_4lsdksD31GaZ09")
    assert not TOKEN_FORMAT["razorpay"].match("pm_abc")
    assert TOKEN_FORMAT["fake"].match("pm_fake_visa_ok")
    assert not TOKEN_FORMAT["fake"].match("pm_visa")


def test_a_card_is_good_until_the_end_of_its_expiry_month() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    assert not is_expired(11, 2026, now)
    assert is_expired(10, 2026, now)
    assert is_expired(12, 2025, now)
    assert not is_expired(1, 2027, now)
