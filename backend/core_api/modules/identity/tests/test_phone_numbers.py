"""R38: phone numbers by country (shared/phone.py): validation, E.164 storage, display."""
import pytest

from shared.phone import format_phone, normalize


@pytest.mark.parametrize("typed,country,e164", [
    ("(208) 555-0123", "US", "+12085550123"), ("208.555.0123", "US", "+12085550123"), ("+1 208 555 0123", "IN", "+12085550123"),
    ("98765 43210", "IN", "+919876543210"), ("098765 43210", "IN", "+919876543210"), ("+91 98765 43210", "US", "+919876543210"),
    ("+919000000101", None, "+919000000101"), ("919000000101", None, "+919000000101"),
])
def test_valid_numbers_are_stored_as_e164(typed: str, country: str | None, e164: str) -> None:
    assert normalize(typed, country) == e164


@pytest.mark.parametrize("typed,country", [
    ("12345", "US"), ("555-0123", "US"), ("(000) 555-0123", "US"), ("+12080000000", "US"),
    ("00000 00000", "IN"), ("98765", "IN"), ("+910000000000", "IN"), ("", "IN"), ("call me", "US"), (None, "US"),
])
def test_invalid_numbers_are_refused(typed: str | None, country: str) -> None:
    assert normalize(typed, country) is None


def test_display_follows_the_country() -> None:
    assert format_phone("+12085550123") == "+1 (208) 555-0123"
    assert format_phone("+919876543210") == "+91 98765 43210"
    assert format_phone("") == "" and format_phone("oops") == "oops"
