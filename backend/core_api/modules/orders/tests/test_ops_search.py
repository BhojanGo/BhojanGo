"""Admin order search: how the search box is read. Found by CI: an order whose
code is all digits (#418292) was searched as a phone number and never found."""
import pytest

from core_api.modules.orders.api.v1.ops import search_terms


@pytest.mark.parametrize(("q", "want"), [
    ("#A9D1F0", ("a9d1f0", True, False)),    # a code, by its hash
    ("a9d1f0", ("a9d1f0", True, False)),     # a code without it
    ("#418292", ("418292", True, False)),    # an all-digit code, by its hash: code only
    ("418292", ("418292", True, True)),      # six digits: a code or the end of a phone, both are tried
    ("9000000101", ("9000000101", True, True)),
    ("+91 9000", ("+91 9000", True, False)),  # not a phone search (too short, not digits): code prefix only
])
def test_search_terms(q: str, want: tuple) -> None:
    assert search_terms(q) == want
