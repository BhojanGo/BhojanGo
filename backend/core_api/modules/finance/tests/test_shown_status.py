"""R27: a week's one status, the same in admin Finance, BhojanGo Kitchen and BhojanGo Delivery.

R26: the week of Nov 9–15 said "On its way" in the apps while the payee had no payout account and
admin Finance said "Waiting for approval / Not paid yet". "On its way" needs a transfer."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from core_api.modules.finance.service.statements import SHOWN_STATUSES, paid_on, shown_status


def test_r26_week_waiting_for_approval_without_a_payout_account_is_never_on_its_way() -> None:
    assert shown_status("pending", "draft", 4251, None, "not_started") == "no_account"
    assert shown_status("pending", "draft", 4251, None, None) == "no_account"


def test_waiting_for_approval_when_the_account_is_ready() -> None:
    assert shown_status("pending", "draft", 4251, None, "ready") == "waiting_approval"


def test_set_up_started_but_not_finished() -> None:
    assert shown_status("pending", "draft", 4251, None, "in_progress") == "onboarding"
    assert shown_status("pending", "draft", 4251, None, "action_needed") == "onboarding"
    assert shown_status("onboarding", "partially_paid", 4251, None, "in_progress") == "onboarding"


def test_after_approval_without_an_account() -> None:
    assert shown_status("no_account", "partially_paid", 4251, None, "not_started") == "no_account"


def test_paid_on_the_transfer_day_in_the_countrys_zone() -> None:
    at = datetime(2026, 11, 17, 3, 30, tzinfo=UTC)  # Monday 20:30 in Boise
    assert shown_status("paid", "paid", 4251, "tr_123", "ready") == "paid"
    assert paid_on("paid", at, ZoneInfo("America/Boise")) == "2026-11-16"
    assert paid_on("paid", at, None) == "2026-11-17"
    assert paid_on("waiting_approval", at, None) is None


def test_on_its_way_only_with_a_transfer() -> None:
    assert shown_status("pending", "approved", 4251, "tr_123", "ready") == "on_its_way"
    for setup in ("ready", "not_started", "in_progress", None):
        for run in ("draft", "approved", "partially_paid", "paid"):
            assert shown_status("pending", run, 4251, None, setup) != "on_its_way"


def test_zero_and_below_zero_weeks() -> None:
    assert shown_status("paid", "paid", 0, None, "not_started") == "nothing_due"
    assert shown_status("carried", "paid", -500, None, "ready") == "carried"
    # A week below zero in a draft run isn't waiting for an account: nothing will be sent.
    assert shown_status("pending", "draft", -500, None, "not_started") == "waiting_approval"


@pytest.mark.parametrize("status", ["failed", "reversed"])
def test_failed_and_reversed_keep_their_note(status: str) -> None:
    assert shown_status(status, "partially_paid", 4251, "tr_1", "ready") == status


def test_approved_ready_and_not_sent_yet() -> None:
    assert shown_status("pending", "approved", 4251, None, "ready") == "not_paid"


def test_every_code_is_listed() -> None:
    seen = {shown_status(st, run, amt, tr, setup)
            for st in ("pending", "paid", "failed", "no_account", "onboarding", "reversed", "carried")
            for run in ("draft", "approved", "partially_paid", "paid")
            for amt in (-1, 0, 1) for tr in (None, "tr") for setup in (None, "not_started", "in_progress", "ready")}
    assert seen <= set(SHOWN_STATUSES)
    assert seen == set(SHOWN_STATUSES)
