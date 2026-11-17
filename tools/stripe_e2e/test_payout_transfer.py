"""Payouts through Stripe Connect Express in Stripe test mode (R10 items 3, 4), against the
throwaway stack tools/stripe_e2e/run.sh starts (harness.py runs every case_* here, in order).
GitHub CI covers the same code with Stripe mocked (core_api/integration/test_connect_payouts.py).

Payouts have their own webhook endpoints: transfer.* on /api/v1/finance/stripe/webhook and
events on connected accounts on /api/v1/finance/stripe/connect/webhook. The harness's
`stripe listen` forwards only to the payments endpoint, so the first case starts a second
`stripe listen` (the harness's pinned CLI in STRIPE_E2E_WORK) with --forward-connect-to; the
CLI signs every session with the same secret, so core-api's STRIPE_WEBHOOK_SECRET verifies
them (finance falls back to it when its own secrets are empty). The last case stops it.

  connect_onboarding_link  the Boise kitchen partner taps "Set up payouts with Stripe": an Express
                           account and an Account Link (a Stripe page). Stripe's "complete your
                           platform profile" error fails it with the Dashboard setting to change.
  connect_payout_transfer  a test connected account that can take transfers (Express dashboard,
                           requirements given through the API with Stripe's documented test values),
                           funded by a charge that is available at once (pm_card_bypassPending =
                           4000 0000 0000 0077); an approved weekly run pays it with a real Transfer
                           (our idempotency key, recorded as paid); the transfer is reversed and the
                           transfer.reversed webhook marks the payout line reversed.
"""
from __future__ import annotations

import subprocess
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

from harness import H

PARTNER, RIDER, FINANCE = "partner.boi@example.com", "rider1.boi@example.com", "finance.us@example.com"
EVENTS = "account.updated,account.application.deauthorized,payout.failed,payout.paid,transfer.created,transfer.updated,transfer.reversed"


def _listen(h: H) -> None:
    """A second `stripe listen` for the payout endpoints (key by env, output to a file never printed)."""
    cli = h.work / "stripe"
    if "listen" in h.state or not cli.exists():
        return
    port = h.core.rsplit(":", 1)[-1]
    log = open(h.work / "listen-payouts.log", "w")  # noqa: SIM115 (closed with the process)
    import os

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
            h.stripe.Account.delete(acct)
        except Exception as e:  # noqa: BLE001 (a test account Stripe already removed)
            print(f"  note: couldn't delete a test account: {type(e).__name__}")


def _created(h: H, acct_id: str) -> None:
    h.state.setdefault("connect_accounts", []).append(acct_id)


def case_connect_onboarding_link(h: H) -> None:
    _listen(h)
    partner = h.api(PARTNER)
    kitchen = h.sql("SELECT r.id FROM restaurants r JOIN users u ON u.id = r.owner_id "
                    f"WHERE u.email = '{PARTNER}' ORDER BY r.name LIMIT 1")[0][0]
    h.sql(f"DELETE FROM payout_accounts WHERE payee_id = '{kitchen}'")
    r = partner.client.post(f"{h.core}/api/v1/finance/payout-accounts", headers=partner.headers,
                            json={"payee_type": "restaurant", "restaurant_id": kitchen})
    if r.status_code == 503 and (r.json().get("detail") or {}).get("code") == "CONNECT_NOT_SET_UP":
        raise AssertionError(r.json()["detail"]["message"])  # names the Dashboard page to finish
    assert r.status_code == 201, f"open account: {r.status_code} {r.text[:300]}"
    body = r.json()
    assert body["provider"] == "stripe_connect", f"the US should pay with Stripe Connect, got {body['provider']}"
    assert (body["onboarding_url"] or "").startswith("https://connect.stripe.com/"), "no Stripe onboarding page"
    ext = h.sql(f"SELECT external_id FROM payout_accounts WHERE id = '{body['id']}'")[0][0]
    _created(h, ext)
    acct = h.stripe.Account.retrieve(ext)
    assert "transfers" in (acct.get("capabilities") or {}), "the transfers capability wasn't requested"
    setup = partner.call("GET", "/finance/payout-accounts/me/setup", 200,
                         params={"payee_type": "restaurant", "restaurant_id": kitchen, "refresh": "true"})
    assert setup["state"] == "in_progress", setup["state"]
    r = partner.client.get(f"{h.core}/api/v1/finance/payout-onboarding", params={"t": "forged.1.x"}, follow_redirects=False)
    assert r.status_code == 302 and "status=expired" in r.headers["location"]


def _test_account(h: H):  # type: ignore[no-untyped-def]
    """Express dashboard, requirements supplied by the platform with Stripe's test values,
    so `transfers` turns active without the hosted pages (https://docs.stripe.com/connect/testing)."""
    email = f"courier-{uuid.uuid4().hex[:8]}@example.com"
    return h.stripe.Account.create(
        country="US", email=email, business_type="individual",
        controller={"stripe_dashboard": {"type": "express"}, "fees": {"payer": "application"},
                    "losses": {"payments": "application"}, "requirement_collection": "application"},
        capabilities={"transfers": {"requested": True}},
        business_profile={"mcc": "4215", "url": "https://bhojango.example", "product_description": "Food delivery with BhojanGo"},
        individual={"first_name": "Test", "last_name": "Courier", "email": email, "phone": "+12085550199",
                    "dob": {"day": 1, "month": 1, "year": 1901}, "ssn_last_4": "0000", "id_number": "000000000",
                    "address": {"line1": "address_full_match", "city": "Boise", "state": "ID", "postal_code": "83702", "country": "US"}},
        tos_acceptance={"date": int(time.time()), "ip": "8.8.8.8"},
        external_account="btok_us_verified",
        metadata={"purpose": "bhojango stripe-e2e connect_payout_transfer"},
    )


def case_connect_payout_transfer(h: H) -> None:
    try:
        _listen(h)
        acct = _test_account(h)
        _created(h, acct.id)
        rider = h.api(RIDER)
        rider_id = rider.user["id"]
        h.sql(f"DELETE FROM payout_accounts WHERE payee_id = '{rider_id}'")
        h.sql("INSERT INTO payout_accounts (id, payee_type, payee_id, provider, external_id, status, country) "
              f"VALUES ('{uuid.uuid4()}', 'rider', '{rider_id}', 'stripe_connect', '{acct.id}', 'pending', 'US')")

        def ready():  # type: ignore[no-untyped-def]
            s = rider.call("GET", "/finance/payout-accounts/me/setup", 200, params={"payee_type": "rider", "refresh": "true"})
            return s["state"] == "ready" and s

        h.wait(ready, 120, 3, "the test connected account to have payouts enabled")

        pi = h.stripe.PaymentIntent.create(amount=5000, currency="usd", payment_method="pm_card_bypassPending", confirm=True,
                                           automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                                           description="bhojango stripe-e2e: funds for a Connect transfer")
        assert pi.status == "succeeded", pi.status

        # A weekly run "prepared by the scheduler" for the delivery partner; a finance admin approves it.
        start = date(1980, 1, 7) + timedelta(weeks=uuid.uuid4().int % 400)
        run_id, st_id = uuid.uuid4(), uuid.uuid4()
        h.sql("INSERT INTO payout_runs (id, country, currency, period_start, period_end, status, totals, created_by) "
              f"VALUES ('{run_id}', 'US', 'USD', '{start}', '{start + timedelta(days=7)}', 'draft', '{{}}'::jsonb, "
              "'00000000-0000-0000-0000-000000000000')")
        h.sql("INSERT INTO payout_statements (id, run_id, payee_type, payee_id, payee_name, currency, amount, summary, lines, status) "
              f"VALUES ('{st_id}', '{run_id}', 'rider', '{rider_id}', 'Stripe e2e', 'USD', 1234, '{{}}'::jsonb, '[]'::jsonb, 'pending')")
        finance = h.api(FINANCE)
        run = finance.call("POST", f"/finance/payout-runs/{run_id}/approve", 200)
        st = next(s for s in run["statements"] if s["id"] == str(st_id))
        assert st["status"] == "paid" and (st["transfer_id"] or "").startswith("tr_"), f"{st['status']}: {st['error']}"
        tr = h.stripe.Transfer.retrieve(st["transfer_id"])
        assert tr.destination == acct.id and tr.amount == 1234 and tr.currency == "usd", (tr.destination, tr.amount)
        assert tr.metadata["payout_statement_id"] == str(st_id)
        print(f"  transfer {tr.id}: 1234 usd to the test connected account")

        h.stripe.Transfer.create_reversal(tr.id)
        if "listen" in h.state:
            def reversed_():  # type: ignore[no-untyped-def]
                d = finance.call("GET", f"/finance/payout-runs/{run_id}", 200)
                return next(s for s in d["statements"] if s["id"] == str(st_id))["status"] == "reversed"

            h.wait(reversed_, 90, 3, "transfer.reversed to mark the payout line reversed")
            assert int(h.sql("SELECT count(*) FROM processed_webhook_events WHERE provider = 'stripe_connect'")[0][0]) >= 1
        else:
            print("  note: no Stripe CLI found in STRIPE_E2E_WORK; the reversal webhook wasn't checked")
    finally:
        _stop(h)
