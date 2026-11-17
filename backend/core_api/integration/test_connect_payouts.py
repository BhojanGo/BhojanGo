"""R10 on Postgres: payouts through Stripe Connect Express with Stripe mocked (the real
thing: tools/stripe_e2e/test_payout_transfer.py in the Railway stripe-e2e job; keys only in Railway).

A Boise kitchen and delivery partner set up payouts from the apps (an Express account,
a fresh onboarding link, the state they see), an admin copies and sends a link, an
approved run waits for onboarding and pays the moment account.updated says payouts
are enabled, a reversed transfer is paid again with a new key, and every webhook event
is applied once. India's provider is untouched (test_payouts.py)."""
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from core_api.integration.test_orders_flow import login

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"
SECRET = "whsec_test_connect"


class MockConnect:
    """Stands in for providers.StripeConnect: same name and shape, no network."""

    name = "stripe_connect"
    hosted_onboarding = True
    accounts: dict[str, dict] = {}
    transfers: list[dict] = []

    async def create_account(self, payee: dict) -> dict:
        acct_id = f"acct_mock_{uuid.uuid4().hex[:10]}"
        MockConnect.accounts[acct_id] = {"id": acct_id, "details_submitted": False, "payouts_enabled": False,
                                         "requirements": {"currently_due": ["external_account"]}, "payee": payee}
        return {"external_id": acct_id, "status": "pending", "onboarding_url": None}

    async def onboarding_link(self, external_id: str, refresh_url: str, return_url: str) -> str:
        assert "/api/v1/finance/payout-onboarding?t=" in refresh_url and "/payouts/done?app=" in return_url
        return f"https://connect.stripe.com/setup/e/{external_id}/{uuid.uuid4().hex[:6]}"

    async def account_state(self, external_id: str) -> dict:
        return MockConnect.accounts[external_id]

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        tr = {"id": f"tr_mock_{uuid.uuid4().hex[:10]}", "destination": external_id, "amount": amount,
              "currency": currency, "key": f"payout-{reference}"}
        MockConnect.transfers.append(tr)
        return tr["id"]


@pytest.fixture
async def client(monkeypatch):  # type: ignore[no-untyped-def]
    from core_api.main import app
    from core_api.modules.finance.service import providers as P
    from shared.config import get_settings
    from shared.db import engine
    from shared.redis import close_redis

    monkeypatch.setitem(P.LIVE, "stripe_connect", MockConnect)
    monkeypatch.setattr(P, "_has_keys", lambda choice: choice == "stripe_connect")
    monkeypatch.setattr(get_settings().payments, "STRIPE_CONNECT_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(get_settings().payments, "STRIPE_PAYOUTS_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(get_settings().payments, "PUBLIC_API_URL", "https://api.test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def _q(sql: str, **kw) -> list:  # type: ignore[no-untyped-def]
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(sql), kw)).all()
        await db.commit()
        return rows


def signed(event: dict) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


async def hook(client: AsyncClient, path: str, kind: str, obj: dict, account: str | None = None, event_id: str | None = None) -> dict:
    event = {"id": event_id or f"evt_{uuid.uuid4().hex[:12]}", "type": kind, "data": {"object": obj},
             **({"account": account} if account else {})}
    body, headers = signed(event)
    r = await client.post(f"/api/v1/finance/stripe/{path}", content=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def us_run(kitchen: str, amount: int) -> tuple[str, str]:
    """An approved-ready US run (made by "the scheduler") with one statement for the kitchen."""
    from core_api.modules.finance.models import PayoutRun, PayoutStatement
    from shared.db import AsyncSessionLocal

    start = date(1990, 1, 1) + timedelta(weeks=uuid.uuid4().int % 500)  # far from real weeks and the access sweep's
    async with AsyncSessionLocal() as db:
        run = PayoutRun(country="US", currency="USD", period_start=start, period_end=start + timedelta(days=7),
                        status="draft", totals={}, created_by=uuid.UUID(int=0))
        db.add(run)
        await db.flush()
        st = PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=uuid.UUID(kitchen), payee_name="Boise Bowl Co.",
                             currency="USD", amount=amount, summary={}, lines=[])
        db.add(st)
        await db.commit()
        return str(run.id), str(st.id)


async def test_connect_onboarding_weekly_transfer_and_webhooks(client: AsyncClient) -> None:
    from core_api.modules.finance.models import PayoutAccount
    from shared.db import AsyncSessionLocal

    kitchen = str((await _q("SELECT r.id FROM restaurants r JOIN users u ON u.id = r.owner_id "
                            "WHERE u.email = 'partner.boi@example.com' ORDER BY r.name LIMIT 1"))[0][0])
    await _q("DELETE FROM payout_accounts WHERE payee_id = :k", k=uuid.UUID(kitchen))
    partner = await login(client, "partner.boi@example.com")

    # The Kitchen app's Payouts screen before set-up: Stripe, on Stripe's pages, not started.
    setup = (await client.get("/api/v1/finance/payout-accounts/me/setup", headers=partner,
                              params={"payee_type": "restaurant", "restaurant_id": kitchen})).json()
    assert (setup["provider"], setup["hosted_onboarding"], setup["state"], setup["account"]) == ("stripe_connect", True, "not_started", None)

    # "Set up payouts with Stripe": an Express account and a fresh link; again: the same account, a new link.
    r = await client.post("/api/v1/finance/payout-accounts", headers=partner, json={"payee_type": "restaurant", "restaurant_id": kitchen})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["state"] == "in_progress" and first["onboarding_url"].startswith("https://connect.stripe.com/")
    again = (await client.post("/api/v1/finance/payout-accounts", headers=partner,
                               json={"payee_type": "restaurant", "restaurant_id": kitchen})).json()
    assert again["id"] == first["id"] and again["onboarding_url"] != first["onboarding_url"]
    acct_id = (await _q("SELECT external_id FROM payout_accounts WHERE id = :i", i=uuid.UUID(first["id"])))[0][0]
    assert MockConnect.accounts[acct_id]["payee"]["type"] == "restaurant"

    # An admin for Boise copies and sends a link that lasts; Hyderabad's ops can't.
    ops_boi, ops_hyd = await login(client, "ops.boi@example.com", ADMIN), await login(client, "ops.hyd@example.com", ADMIN)
    path = f"/api/v1/finance/payees/restaurant/{kitchen}/payout-account"
    assert (await client.post(f"{path}/link", headers=ops_hyd, json={"send": True})).status_code == 403
    r = await client.post(f"{path}/link", headers=ops_boi, json={"send": True})
    assert r.status_code == 200, r.text
    sent = r.json()
    assert sent["link"].startswith("https://api.test/api/v1/finance/payout-onboarding?t=") and sent["sent"] is True
    assert sent["state"] == "in_progress" and sent["expires_in_days"] == 7
    events = await _q("SELECT envelope FROM outbox_events WHERE event_type = 'payout.setup_link' AND aggregate_id = :k", k=kitchen)
    assert any(e["payload"]["link"] == sent["link"] for (e,) in events)

    # The link opens a fresh Stripe page; a forged one goes to the website's page instead.
    r = await client.get("/api/v1/finance/payout-onboarding", params={"t": sent["link"].split("t=")[1]})
    assert r.status_code == 302 and r.headers["location"].startswith(f"https://connect.stripe.com/setup/e/{acct_id}/")
    r = await client.get("/api/v1/finance/payout-onboarding", params={"t": "forged.123.abc"})
    assert r.status_code == 302 and r.headers["location"].endswith("/payouts/done?status=expired")

    # Approved while the kitchen is still onboarding: the statement waits.
    run_id, st_id = await us_run(kitchen, 4250)
    finance_us = await login(client, "finance.us@example.com", ADMIN)
    r = await client.post(f"/api/v1/finance/payout-runs/{run_id}/approve", headers=finance_us)
    assert r.status_code == 200, r.text
    st = next(s for s in r.json()["statements"] if s["id"] == st_id)
    assert (st["status"], st["payout_setup"]) == ("onboarding", "in_progress")

    # Stripe: details submitted, something still due → action needed (and nothing paid).
    obj = {"id": acct_id, "details_submitted": True, "payouts_enabled": False,
           "requirements": {"currently_due": ["individual.verification.document"], "disabled_reason": "requirements.past_due"}}
    assert (await hook(client, "connect/webhook", "account.updated", obj, account=acct_id))["result"] == "account_updated"
    setup = (await client.get("/api/v1/finance/payout-accounts/me/setup", headers=partner,
                              params={"payee_type": "restaurant", "restaurant_id": kitchen})).json()
    assert setup["state"] == "action_needed" and setup["account"]["requirements_due"] == ["individual.verification.document"]

    # Payouts enabled: the waiting statement is paid at once, keyed by the statement and attempt 0.
    obj = {"id": acct_id, "details_submitted": True, "payouts_enabled": True, "requirements": {"currently_due": []}}
    evt = f"evt_{uuid.uuid4().hex[:12]}"
    assert (await hook(client, "connect/webhook", "account.updated", obj, account=acct_id, event_id=evt))["result"] == "account_ready"
    assert (await hook(client, "connect/webhook", "account.updated", obj, account=acct_id, event_id=evt))["result"] == "already_processed"
    tr = MockConnect.transfers[-1]
    assert tr["destination"] == acct_id and tr["amount"] == 4250 and tr["key"] == f"payout-{run_id}:{st_id}:0"
    detail = (await client.get(f"/api/v1/finance/payout-runs/{run_id}", headers=finance_us)).json()
    st = next(s for s in detail["statements"] if s["id"] == st_id)
    assert (st["status"], st["transfer_id"], st["payout_setup"], detail["status"]) == ("paid", tr["id"], "ready", "paid")

    # Reversed in Stripe → reversed; retry sends a new transfer with a new key.
    rev = {"id": tr["id"], "amount": 4250, "amount_reversed": 4250, "reversed": True,
           "metadata": {"payout_statement_id": st_id, "payout_run_id": run_id}}
    assert (await hook(client, "webhook", "transfer.reversed", rev))["result"] == "transfer_reversed"
    detail = (await client.get(f"/api/v1/finance/payout-runs/{run_id}", headers=finance_us)).json()
    assert detail["status"] == "partially_paid"  # finance sees "Retry unpaid"
    assert next(s for s in detail["statements"] if s["id"] == st_id)["status"] == "reversed"
    r = await client.post(f"/api/v1/finance/payout-runs/{run_id}/retry", headers=finance_us)
    assert r.status_code == 200, r.text
    assert MockConnect.transfers[-1]["key"] == f"payout-{run_id}:{st_id}:1"
    assert next(s for s in r.json()["statements"] if s["id"] == st_id)["status"] == "paid"

    # A bank payout that failed on the connected account → action needed in the app and admin.
    assert (await hook(client, "connect/webhook", "payout.failed", {"id": "po_1", "failure_message": "The bank account is closed"},
                       account=acct_id))["result"] == "bank_payout_failed"
    admin_view = (await client.get(path, headers=finance_us)).json()
    assert admin_view["state"] == "action_needed" and admin_view["account"]["payout_error"] == "The bank account is closed"
    assert (await client.get(path, headers=await login(client, "finance.in@example.com", ADMIN))).status_code == 403

    # A bad signature is refused.
    r = await client.post("/api/v1/finance/stripe/connect/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=bad"})
    assert r.status_code == 400
    async with AsyncSessionLocal() as db:
        a = (await db.execute(select(PayoutAccount).where(PayoutAccount.external_id == acct_id))).scalar_one()
        assert a.payouts_enabled and a.status == "active"


async def test_a_delivery_partner_sets_up_from_the_delivery_app(client: AsyncClient) -> None:
    rider = await login(client, "rider1.boi@example.com")
    rider_id = str((await _q("SELECT id FROM users WHERE email = 'rider1.boi@example.com'"))[0][0])
    await _q("DELETE FROM payout_accounts WHERE payee_id = :k", k=uuid.UUID(rider_id))
    r = await client.post("/api/v1/finance/payout-accounts", headers=rider, json={"payee_type": "rider"})
    assert r.status_code == 201, r.text
    assert r.json()["onboarding_url"].startswith("https://connect.stripe.com/")
    acct_id = (await _q("SELECT external_id FROM payout_accounts WHERE payee_id = :k", k=uuid.UUID(rider_id)))[0][0]
    MockConnect.accounts[acct_id].update(details_submitted=True, payouts_enabled=True, requirements={"currently_due": []})
    # Back from Stripe: the app asks again with refresh, before any webhook.
    setup = (await client.get("/api/v1/finance/payout-accounts/me/setup", headers=rider,
                              params={"payee_type": "rider", "refresh": True})).json()
    assert setup["state"] == "ready" and setup["provider"] == "stripe_connect"
    mine = (await client.get("/api/v1/finance/payout-accounts/me", headers=rider)).json()
    assert [a["state"] for a in mine] == ["ready"]
    # Another delivery partner's set-up is not theirs to see.
    other = str((await _q("SELECT id FROM users WHERE email = 'rider2.boi@example.com'"))[0][0])
    assert (await client.get("/api/v1/finance/payout-accounts/me/setup", headers=rider,
                             params={"payee_type": "restaurant", "restaurant_id": other})).status_code == 404
