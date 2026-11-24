"""R37: every bill fixture (packages/ui/test/fixtures/bills.json: US and India, from the quote engine; the web,
app and shared bill tests read the same file), printed as the receipt and messages print money (exact paise),
adds up to the printed total."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from core_api.modules.orders.service import receipt as R
from shared.money import format_money

FIXTURES = Path(__file__).resolve().parents[5] / "packages" / "ui" / "test" / "fixtures" / "bills.json"
BILLS = json.loads(FIXTURES.read_text(encoding="utf-8"))


def amount(shown: str) -> Decimal:
    sign = -1 if shown.startswith(("−", "-")) else 1
    return sign * Decimal("".join(ch for ch in shown if ch.isdigit() or ch == "."))


def test_fixtures_cover_both_countries() -> None:
    assert {b["currency"] for b in BILLS} == {"INR", "USD"} and len(BILLS) >= 6


@pytest.mark.parametrize("bill", BILLS, ids=[b["name"] for b in BILLS])
def test_printed_lines_add_up_to_the_printed_total(bill: dict) -> None:
    shown = [format_money(ln["amount"], bill["currency"], bill["locale"]) for ln in bill["lines"]]
    assert sum((amount(s) for s in shown), Decimal(0)) == amount(format_money(bill["total"], bill["currency"], bill["locale"]))
    rows = [r for r in R.bill_rows(bill["lines"], bill["currency"]) if r[2] != "included"]
    assert sum((amount(r[2]) for r in rows), Decimal(0)) == Decimal(bill["total"]), rows
