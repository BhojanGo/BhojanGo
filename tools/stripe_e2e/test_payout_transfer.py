"""Payouts through Stripe Connect Express in Stripe test mode (R10 item 3, R11 item 1), against
the throwaway stack tools/stripe_e2e/run.sh starts (harness.py runs every case_* here, in order).
GitHub CI covers the same code with Stripe mocked (core_api/integration/test_connect_payouts.py).

Payouts have their own webhook endpoints: transfer.* on /api/v1/finance/stripe/webhook and
events on connected accounts on /api/v1/finance/stripe/connect/webhook. The harness's
`stripe listen` forwards only to the payments endpoint, so the first case starts a second
`stripe listen` (the harness's pinned CLI in STRIPE_E2E_WORK) with --forward-connect-to; the
CLI signs every session with the same secret, so core-api's STRIPE_WEBHOOK_SECRET verifies
them (finance falls back to it when its own secrets are empty). The last case stops it.

  connect_onboarding_link  the Boise Bowl Co. kitchen partner and a Boise delivery partner each tap
                           "Set up payouts with Stripe": an Express account (Accounts v2) and an
                           Account Link to Stripe's hosted pages.
  connect_payout_transfer  the weekly payout for real: an order paid through Stripe is delivered by
                           the delivery partner; a finance admin prepares the run for this week
                           (POST /finance/payout-runs, the code the scheduler's draft uses) and a
                           second approves it; the kitchen and the delivery partner are each paid
                           with a real Transfer; admin Finance's run page (GET /finance/payout-runs/{id})
                           shows both paid with their transfer ids; a reversal's transfer.reversed
                           webhook marks the delivery partner's line reversed.

Stripe's hosted onboarding asks a person to accept Stripe's terms and shows automated browsers a
CAPTCHA, so by default the accounts paid here are test accounts whose requirements the platform
supplies through the API with Stripe's documented test values (https://docs.stripe.com/connect/testing).
To pay Express accounts a person onboarded on Stripe's pages with test data instead, set
STRIPE_E2E_EXPRESS_KITCHEN and STRIPE_E2E_EXPRESS_RIDER (their acct_ ids) on the runner; those are kept.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

from harness import H

RIDER, FINANCE, MAKER = "rider1.boi@example.com", "finance.us@example.com", "admin@example.com"
EVENTS = "account.updated,account.application.deauthorized,payout.failed,payout.paid,transfer.created,transfer.updated,transfer.reversed"


def _listen(h: H) -> None:
    """A second `stripe listen` for the payout endpoints (key by env, output to a file never printed)."""
    cli = h.work / "stripe"
    if "listen" in h.state or not cli.exists():
        return
    port = h.core.rsplit(":", 1)[-1]
    log = open(h.work / "listen-payouts.log", "w")  # noqa: SIM115 (closed with the process)
    p = subprocess.Popen([str(cli), "listen", "--events", EVENTS,
                          "--forward-to", f"localhost:{port}/api/v1/finance/stripe/webhook",
                          "--forward-connect-to", f"localhost:{port}/api/v1/finance/stripe/connect/webhook"],
                         env={**os.environ, "STRIPE_API_KEY": os.environ["STRIPE_SECRET_KEY"]}, stdout=log, stderr=log)
    h.state["listen"] = (p, log)
    import atexit

    atexit.register(lambda: _stop(h))  # even when only the first case runs
    h.wait(lambda: "Ready!" in Path(log.name).read_text(errors="ignore"), 30, 1, "the payouts stripe listen")


def _stop(h: H) -> None:
    if "listen" in h.state:
        p, log = h.state.pop("listen")
        p.terminate()
        log.close()
    for acct in h.state.pop("connect_accounts", []):
        try:
            h.stripe.StripeClient(h.stripe.api_key).v2.core.accounts.close(acct, {"applied_configurations": ["recipient"]})
        except Exception as e:  # noqa: BLE001 (a test account Stripe already closed)
            print(f"  note: couldn't close a test account: {type(e).__name__}")


def _created(h: H, acct_id: str) -> None:
    h.state.setdefault("connect_accounts", []).append(acct_id)


def _kitchen(h: H) -> tuple[str, str]:
    """(restaurant id, owner's email) of Boise Bowl Co., the kitchen the payment cases order from."""
    rid, email = h.sql("SELECT r.id, u.email FROM restaurants r JOIN users u ON u.id = r.owner_id "
                       "WHERE r.name = 'Boise Bowl Co.' LIMIT 1")[0]
    return rid, email


def _open(h: H, who, body: dict, setup_params: dict) -> str:  # type: ignore[no-untyped-def]
    """Open the payee's Stripe account through our API, as the payee; returns its acct_ id."""
    r = who.client.post(f"{h.core}/api/v1/finance/payout-accounts", headers=who.headers, json=body)
    if r.status_code == 503 and (r.json().get("detail") or {}).get("code") == "CONNECT_NOT_SET_UP":
        raise AssertionError(r.json()["detail"]["message"])  # names the Dashboard page to finish
    assert r.status_code == 201, f"open account: {r.status_code} {r.text[:300]}"
    out = r.json()
    assert out["provider"] == "stripe_connect", f"the US should pay with Stripe Connect, got {out['provider']}"
    assert (out["onboarding_url"] or "").startswith("https://connect.stripe.com/"), "no Stripe onboarding page"
    ext = h.sql(f"SELECT external_id FROM payout_accounts WHERE id = '{out['id']}'")[0][0]
    _created(h, ext)
    acct = h.stripe.Account.retrieve(ext).to_dict()
    assert "transfers" in (acct.get("capabilities") or {}), "the transfers capability wasn't requested"
    v2 = h.stripe.StripeClient(h.stripe.api_key).v2.core.accounts.retrieve(ext)
    assert v2.dashboard == "express", f"expected an Express account, got {v2.dashboard}"
    setup = who.call("GET", "/finance/payout-accounts/me/setup", 200, params={**setup_params, "refresh": "true"})
    assert setup["state"] == "in_progress", setup["state"]
    return ext


def case_connect_onboarding_link(h: H) -> None:
    _listen(h)
    kitchen, owner_email = _kitchen(h)
    owner, rider = h.api(owner_email), h.api(RIDER)
    h.sql(f"DELETE FROM payout_accounts WHERE payee_id IN ('{kitchen}', '{rider.user['id']}')")
    _open(h, owner, {"payee_type": "restaurant", "restaurant_id": kitchen}, {"payee_type": "restaurant", "restaurant_id": kitchen})
    _open(h, rider, {"payee_type": "rider"}, {"payee_type": "rider"})
    print("  Express accounts (Accounts v2) for the kitchen and the delivery partner, each with a Stripe onboarding link")
    r = rider.client.get(f"{h.core}/api/v1/finance/payout-onboarding", params={"t": "forged.1.x"}, follow_redirects=False)
    assert r.status_code == 302 and "status=expired" in r.headers["location"]


def _test_account(h: H, name: str, mcc: str) -> str:
    """A connected account that takes transfers without Stripe's hosted pages: requirements collected
    by the platform (no Stripe dashboard) with Stripe's test values, terms accepted through the API,
    a test bank (https://docs.stripe.com/connect/testing)."""
    email = f"payee-{uuid.uuid4().hex[:8]}@example.com"
    a = h.stripe.StripeClient(h.stripe.api_key).v2.core.accounts.create({
        "contact_email": email, "display_name": name, "dashboard": "none",
        "identity": {"country": "US", "entity_type": "individual", "individual": {
            "given_name": "Test", "surname": "Payee", "email": email, "phone": "+12085550199",
            "date_of_birth": {"day": 1, "month": 1, "year": 1901},
            "address": {"line1": "address_full_match", "city": "Boise", "state": "ID", "postal_code": "83702", "country": "US"},
            "id_numbers": [{"type": "us_ssn", "value": "000000000"}]},
            "attestations": {"terms_of_service": {"account": {
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ip": "8.8.8.8"}}}},
        "defaults": {"responsibilities": {"fees_collector": "application", "losses_collector": "application"}},
        "configuration": {"recipient": {"capabilities": {"stripe_balance": {"stripe_transfers": {"requested": True}}}}},
        "metadata": {"purpose": "bhojango stripe-e2e connect_payout_transfer"},
    })
    _created(h, a.id)
    h.stripe.Account.modify(a.id, business_profile={"url": "https://bhojango.example", "mcc": mcc},
                            external_account="btok_us_verified")
    return a.id


def _paid_order(h: H) -> dict:
    """The order the card case paid (or one paid now with 4242 when this case runs alone)."""
    if "paid" in h.state:
        return h.state["paid"]["order"]
    customer = h.api("customer1.boi@example.com")
    rest, address, q, cart = h.boise_quote(customer)
    order = h.place(customer, rest, address, q, cart)
    pi_id = h.initiate(customer, order["id"])["checkout"]["payment_intent_client_secret"].split("_secret_")[0]
    h.stripe.PaymentIntent.confirm(pi_id, payment_method="pm_card_visa", return_url="https://example.com/return")
    h.wait_payment(customer, order["id"], "succeeded")
    return order


def case_connect_payout_transfer(h: H) -> None:
    try:
        _listen(h)
        kitchen, owner_email = _kitchen(h)
        owner, rider = h.api(owner_email), h.api(RIDER)
        rider_id = rider.user["id"]

        # Accounts that can take transfers (module docstring) behind the two payees' payout accounts.
        human = {k: os.environ.get(f"STRIPE_E2E_EXPRESS_{k.upper()}", "") for k in ("kitchen", "rider")}
        accts = {"kitchen": human["kitchen"] or _test_account(h, "Boise Bowl Co.", "5812"),
                 "rider": human["rider"] or _test_account(h, "Jake Miller", "4215")}
        for kind, (ptype, pid) in (("kitchen", ("restaurant", kitchen)), ("rider", ("rider", rider_id))):
            h.sql(f"DELETE FROM payout_accounts WHERE payee_id = '{pid}'")
            h.sql("INSERT INTO payout_accounts (id, payee_type, payee_id, provider, external_id, status, country) "
                  f"VALUES ('{uuid.uuid4()}', '{ptype}', '{pid}', 'stripe_connect', '{accts[kind]}', 'pending', 'US')")
        print(f"  paying {'Express accounts onboarded on Stripe with test data' if all(human.values()) else 'test connected accounts'}")
        h.wait(lambda: owner.call("GET", "/finance/payout-accounts/me/setup", 200, params={
            "payee_type": "restaurant", "restaurant_id": kitchen, "refresh": "true"})["state"] == "ready",
            120, 3, "the kitchen's payouts to be ready")
        h.wait(lambda: rider.call("GET", "/finance/payout-accounts/me/setup", 200, params={
            "payee_type": "rider", "refresh": "true"})["state"] == "ready", 120, 3, "the delivery partner's payouts to be ready")

        # The delivery: the order paid through Stripe, delivered by the delivery partner last week
        # (Wednesday noon in Boise): a run pays only a week that has ended (R12).
        order = _paid_order(h)
        monday = date.fromisoformat(h.sql("SELECT (date_trunc('week', now() AT TIME ZONE 'America/Boise'))::date")[0][0])
        monday -= timedelta(days=7)
        wednesday = f"(TIMESTAMP '{monday + timedelta(days=2)} 12:00' AT TIME ZONE 'America/Boise')"
        h.sql(f"UPDATE orders SET status = 'delivered', driver_id = '{rider_id}', created_at = {wednesday} - interval '40 minutes', "
              f"rider_assigned_at = {wednesday} - interval '25 minutes', picked_up_at = {wednesday} - interval '12 minutes', "
              f"actual_delivery_time = {wednesday} WHERE id = '{order['id']}'")

        # Money in the platform's balance to transfer (4000 0000 0000 0077: "available at once", but
        # Stripe's available balance shows it a few seconds later; transfers before that are refused).
        def available() -> int:
            return sum(b["amount"] for b in h.stripe.Balance.retrieve().to_dict()["available"] if b["currency"] == "usd")

        before = available()
        pi = h.stripe.PaymentIntent.create(amount=10000, currency="usd", payment_method="pm_card_bypassPending", confirm=True,
                                           automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                                           description="bhojango stripe-e2e: funds for Connect transfers")
        assert pi.status == "succeeded", pi.status
        h.wait(lambda: available() >= before + 9000, 120, 3, "the funding charge to reach the available balance")

        # Last week's run (Boise's Monday to Sunday), prepared by one admin and approved by
        # a second (the run refuses one person doing both). This week can't be prepared yet.
        maker, checker = h.api(MAKER), h.api(FINANCE)
        maker.call("POST", "/finance/payout-runs", 409, json={
            "country": "US", "period_start": str(monday + timedelta(days=7)), "period_end": str(monday + timedelta(days=14))})
        run = maker.call("POST", "/finance/payout-runs", 201, json={
            "country": "US", "period_start": str(monday), "period_end": str(monday + timedelta(days=7))})
        run = checker.call("POST", f"/finance/payout-runs/{run['id']}/approve", 200)
        ours = {s["payee_type"]: s for s in run["statements"]
                if (s["payee_type"], s["payee_id"]) in {("restaurant", kitchen), ("rider", rider_id)}}
        assert set(ours) == {"restaurant", "rider"}, f"the delivered order didn't reach both statements: {sorted(ours)}"
        for kind, st in ours.items():
            assert st["status"] == "paid" and (st["transfer_id"] or "").startswith("tr_"), f"{kind}: {st['status']} {st['error']}"
            tr = h.stripe.Transfer.retrieve(st["transfer_id"])
            cents = int(h.sql(f"SELECT amount FROM payout_statements WHERE id = '{st['id']}'")[0][0])
            want = accts["kitchen" if kind == "restaurant" else "rider"]
            assert (tr.destination, tr.amount, tr.currency) == (want, cents, "usd"), (tr.destination, tr.amount, cents)
            assert tr.metadata["payout_statement_id"] == st["id"]
            print(f"  {kind}: transfer {tr.id}, {cents} cents")

        # What admin Finance's run page shows.
        page = checker.call("GET", f"/finance/payout-runs/{run['id']}", 200)
        shown = {s["payee_type"]: s for s in page["statements"] if s["id"] in {st["id"] for st in ours.values()}}
        assert set(shown) == {"restaurant", "rider"}, sorted(shown)
        for kind, s in shown.items():
            assert s["status"] == "paid" and s["transfer_id"] == ours[kind]["transfer_id"], (kind, s["status"])
            assert s["payout_setup"] == "ready", (kind, s["payout_setup"])
        print(f"  admin Finance: run {page['status']}, both lines paid with their transfer ids")

        h.stripe.Transfer.create_reversal(ours["rider"]["transfer_id"])
        if "listen" in h.state:
            def reversed_():  # type: ignore[no-untyped-def]
                d = checker.call("GET", f"/finance/payout-runs/{run['id']}", 200)
                return next(s for s in d["statements"] if s["id"] == ours["rider"]["id"])["status"] == "reversed"

            h.wait(reversed_, 90, 3, "transfer.reversed to mark the payout line reversed")
            assert int(h.sql("SELECT count(*) FROM processed_webhook_events WHERE provider = 'stripe_connect'")[0][0]) >= 1
            # The Delivery app's line: sent back, the amount, and the date it's paid again (R12).
            mine = next(s for s in rider.call("GET", "/finance/statements/me", 200) if s["id"] == ours["rider"]["id"])
            assert mine["status"] == "reversed" and date.fromisoformat(mine["repay_on"]) >= date.today() - timedelta(days=1), mine
            print(f"  the delivery partner sees: sent back, paid again on {mine['repay_on']}")
        else:
            print("  note: no Stripe CLI found in STRIPE_E2E_WORK; the reversal webhook wasn't checked")
    finally:
        _stop(h)
