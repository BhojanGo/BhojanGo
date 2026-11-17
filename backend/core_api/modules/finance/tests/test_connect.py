"""Stripe Connect Express payouts (R10) with Stripe mocked: what we ask Stripe for,
how its answers and errors land, the set-up state people see, and signed links."""
import asyncio
import uuid
from types import SimpleNamespace

import pytest

from core_api.modules.finance.models import PayoutAccount
from core_api.modules.finance.service import connect as C
from core_api.modules.finance.service import providers as P


class StripeErr(Exception):
    def __init__(self, msg: str, http_status: int | None) -> None:
        super().__init__(msg)
        self.http_status = http_status
        self.user_message = None


class FakeStripe:
    """Records every call; answers like Stripe's SDK."""

    StripeError = StripeErr

    def __init__(self, fail: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail
        self.Account = SimpleNamespace(create=self._rec("Account.create", SimpleNamespace(id="acct_123")),
                                       retrieve=self._rec("Account.retrieve", {"id": "acct_123", "payouts_enabled": True,
                                                                               "details_submitted": True}))
        self.AccountLink = SimpleNamespace(create=self._rec("AccountLink.create", SimpleNamespace(url="https://connect.stripe.com/setup/e/x")))
        self.Transfer = SimpleNamespace(create=self._rec("Transfer.create", SimpleNamespace(id="tr_1")))

    def _rec(self, name: str, answer):  # type: ignore[no-untyped-def]
        def call(*args, **kw):  # type: ignore[no-untyped-def]
            self.calls.append((name, {"args": args, **kw}))
            if self.fail:
                raise self.fail
            return answer
        return call


@pytest.fixture
def stripe(monkeypatch):  # type: ignore[no-untyped-def]
    fake = FakeStripe()
    monkeypatch.setattr(P, "_stripe", lambda: fake)
    return fake


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def test_express_account_for_a_delivery_partner(stripe) -> None:  # type: ignore[no-untyped-def]
    out = run(P.StripeConnect().create_account({"type": "rider", "id": "u1", "country": "US", "email": "jake@example.com"}))
    assert out == {"external_id": "acct_123", "status": "pending", "onboarding_url": None}
    name, kw = stripe.calls[0]
    assert name == "Account.create" and kw["type"] == "express" and kw["country"] == "US"
    assert kw["capabilities"] == {"transfers": {"requested": True}} and kw["business_type"] == "individual"
    assert kw["business_profile"]["mcc"] == "4215" and kw["metadata"] == {"payee_type": "rider", "payee_id": "u1"}
    assert kw["idempotency_key"] == "payout-account-rider-u1"  # a retried create never opens a second account


def test_a_kitchen_chooses_company_or_sole_trader_on_stripes_pages(stripe) -> None:  # type: ignore[no-untyped-def]
    run(P.StripeConnect().create_account({"type": "restaurant", "id": "k1", "country": "US", "name": "Boise Bowl Co."}))
    kw = stripe.calls[0][1]
    assert "business_type" not in kw and kw["business_profile"] == {
        "mcc": "5812", "product_description": "Food sold through BhojanGo", "name": "Boise Bowl Co."}


def test_onboarding_link_and_transfer_keys(stripe) -> None:  # type: ignore[no-untyped-def]
    url = run(P.StripeConnect().onboarding_link("acct_123", "https://api/refresh", "https://web/payouts/done?app=kitchen"))
    assert url.startswith("https://connect.stripe.com/")
    assert stripe.calls[0][1] | {} == {"args": (), "account": "acct_123", "type": "account_onboarding",
                                       "refresh_url": "https://api/refresh", "return_url": "https://web/payouts/done?app=kitchen"}
    run_id, st_id = uuid.uuid4(), uuid.uuid4()
    assert run(P.StripeConnect().transfer("acct_123", 1234, "USD", f"{run_id}:{st_id}:2")) == "tr_1"
    kw = stripe.calls[1][1]
    assert kw["amount"] == 1234 and kw["currency"] == "usd" and kw["destination"] == "acct_123"
    assert kw["idempotency_key"] == f"payout-{run_id}:{st_id}:2"  # the payout line and its attempt
    assert kw["metadata"] == {"payout_run_id": str(run_id), "payout_statement_id": str(st_id)}
    assert kw["transfer_group"] == f"payout-run-{run_id}"


def test_platform_profile_not_done_says_exactly_what_to_change(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake = FakeStripe(StripeErr("Please review the responsibilities of managing losses for connected accounts at "
                                "https://dashboard.stripe.com/settings/connect/platform-profile.", 400))
    monkeypatch.setattr(P, "_stripe", lambda: fake)
    with pytest.raises(P.ConnectSetupError, match="Platform profile"):
        run(P.StripeConnect().create_account({"type": "rider", "id": "u1", "country": "US"}))
    fake.fail = StripeErr("You can only create new accounts if you've signed up for Connect", 400)
    with pytest.raises(P.ConnectSetupError):
        run(P.StripeConnect().create_account({"type": "rider", "id": "u1", "country": "US"}))


def test_refused_is_final_and_no_answer_is_not(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake = FakeStripe(StripeErr("Insufficient funds in Stripe account", 400))
    monkeypatch.setattr(P, "_stripe", lambda: fake)
    with pytest.raises(P.PayoutError) as e:
        run(P.StripeConnect().transfer("acct_1", 100, "USD", "r:s:0"))
    assert e.value.final  # a new attempt gets a new key
    fake.fail = StripeErr("Connection reset", None)
    with pytest.raises(P.PayoutError) as e:
        run(P.StripeConnect().transfer("acct_1", 100, "USD", "r:s:0"))
    assert not e.value.final  # unknown outcome: the retry reuses the key, never pays twice


def acct(**kw) -> PayoutAccount:  # type: ignore[no-untyped-def]
    base = {"id": uuid.uuid4(), "payee_type": "rider", "payee_id": uuid.uuid4(), "provider": "stripe_connect",
            "external_id": "acct_1", "status": "pending", "country": "US", "details_submitted": False,
            "payouts_enabled": False, "requirements_due": [], "disabled_reason": None, "payout_error": None}
    return PayoutAccount(**{**base, **kw})


def test_states_people_see() -> None:
    assert C.state(None) == "not_started"
    assert C.state(acct()) == "in_progress"  # opened, Stripe's pages not finished
    assert C.state(acct(details_submitted=True, disabled_reason="requirements.pending_verification")) == "in_progress"
    assert C.state(acct(details_submitted=True, requirements_due=["individual.verification.document"],
                        disabled_reason="requirements.past_due")) == "action_needed"
    assert C.state(acct(payouts_enabled=True, details_submitted=True, status="active")) == "ready"
    assert C.state(acct(payouts_enabled=True, status="active", payout_error="Bank account closed")) == "action_needed"
    assert C.state(acct(status="restricted", disabled_reason="rejected.fraud", details_submitted=True)) == "action_needed"


def test_account_updated_fields_land_and_ready_is_reported_once() -> None:
    a = acct()
    obj = {"id": "acct_1", "details_submitted": True, "payouts_enabled": False,
           "requirements": {"currently_due": ["external_account"], "past_due": ["external_account", "tos_acceptance.date"],
                            "disabled_reason": "requirements.past_due"}}
    assert C.apply_account(a, obj) is False
    assert a.requirements_due == ["external_account", "tos_acceptance.date"] and a.status == "restricted"
    assert C.state(a) == "action_needed"
    ready = {"id": "acct_1", "details_submitted": True, "payouts_enabled": True, "requirements": {"currently_due": []}}
    assert C.apply_account(a, ready) is True and a.status == "active" and C.state(a) == "ready"
    assert C.apply_account(a, ready) is False  # already ready: nothing new to pay


def test_signed_links_expire_and_cannot_be_forged() -> None:
    aid = uuid.uuid4()
    t = C.make_token(aid, days=7, now=1_000_000)
    assert C.read_token(t, now=1_000_000 + 6 * 86400) == aid
    assert C.read_token(t, now=1_000_000 + 8 * 86400) is None  # expired
    body, sig = t.rsplit(".", 1)
    assert C.read_token(f"{uuid.uuid4().hex}.{body.split('.')[1]}.{sig}", now=1_000_000) is None  # another account
    assert C.read_token("not-a-token") is None and C.read_token("a.b.c") is None


def test_links_point_at_our_pages(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = SimpleNamespace(payments=SimpleNamespace(PUBLIC_API_URL="https://api.example/"),
                        identity=SimpleNamespace(PUBLIC_WEB_URL="https://web.example"), INTERNAL_SERVICE_SECRET="k")
    monkeypatch.setattr(C, "get_settings", lambda: s)
    a = acct(payee_type="restaurant")
    assert C.kept_link(a).startswith("https://api.example/api/v1/finance/payout-onboarding?t=")
    assert C.return_url(a) == "https://web.example/payouts/done?app=kitchen"
    assert C.return_url(acct()) == "https://web.example/payouts/done?app=delivery"


def test_fake_accounts_are_ready_at_once() -> None:
    a = acct(provider="fake", status="active")
    C.mark_created(a)
    assert C.state(a) == "ready"
    b = acct(provider="razorpay_route")
    C.mark_created(b)
    assert C.state(b) == "in_progress"
