"""Stripe test mode, for real: payouts through Stripe Connect Express (R10 items 3, 4).

A case file for the `stripe-e2e` Railway job (tools/railway/qa-job.sh; harness in
tools/stripe_e2e/, owned by the Stripe payments workstream). Never runs in GitHub CI:
the Stripe keys live only in Railway sealed variables. GitHub CI covers the same code
with Stripe mocked (core_api/integration/test_connect_payouts.py).

Contract with the harness (until its entry point documents another one):
    env  STRIPE_SECRET_KEY   sk_test_… (refused otherwise; never printed)
         STRIPE_E2E_API_URL  the throwaway core-api the harness started (default http://localhost:8001),
                             with PAYOUT_PROVIDER=auto and STRIPE_WEBHOOK_SECRET = the Stripe CLI's secret
         DATABASE_URL        the throwaway database (its name must contain "e2e"), migrated and base-seeded
    CASES  [(name, async fn(ctx) -> None)]: an AssertionError (or any exception) is a FAIL
    run()  runs every case, prints "PASS <name>" / "FAIL <name>: why" and returns True when all pass
Run alone:  cd backend && uv run python ../tools/stripe_e2e/test_payout_transfer.py

Webhooks: payouts have their own endpoints (/api/v1/finance/stripe/webhook for transfer.*,
/api/v1/finance/stripe/connect/webhook for events on connected accounts). When the
`stripe` CLI is on PATH this file starts its own `stripe listen` forwarding there (the CLI
signs every session with the same secret, so the harness's STRIPE_WEBHOOK_SECRET verifies
them); STRIPE_E2E_CONNECT_LISTEN=0 turns that off if the harness forwards them itself.

Cases:
  connect_onboarding_link  the Boise kitchen partner taps "Set up payouts with Stripe": an Express
                           account and an Account Link (a Stripe page). Stripe's "complete your platform
                           profile" error fails it with the exact Dashboard setting to change.
  connect_payout_transfer  a test connected account that can take transfers (Express dashboard,
                           requirements given through the API with Stripe's test values, as Stripe
                           documents for testing), funded by a charge with the "available at once" test
                           card (pm_card_bypassPending = 4000 0000 0000 0077); an approved weekly run
                           pays it: a real Transfer with our idempotency key, recorded as paid; then the
                           transfer is reversed and the transfer.reversed webhook marks the line reversed.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "backend"))
sys.path.insert(0, str(HERE.parents[1]))

ADMIN_PW = "BhojanGoAdmin1"
PW = "BhojanGo123"
SYSTEM = uuid.UUID(int=0)  # a run "prepared by the scheduler", so a finance admin may approve it


@dataclass
class Ctx:
    api: str
    created_accounts: list[str] = field(default_factory=list)
    cleanup_sql: list[tuple[str, dict]] = field(default_factory=list)


def _stripe():  # type: ignore[no-untyped-def]
    import stripe

    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    return stripe


async def _db(sql: str, **kw):  # type: ignore[no-untyped-def]
    import asyncpg

    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    try:
        return await conn.fetch(sql, *kw.values()) if kw else await conn.fetch(sql)
    finally:
        await conn.close()


async def _login(client, email: str, password: str = PW) -> dict:  # type: ignore[no-untyped-def]
    from core_api.modules.identity.tests.signin import login_response

    r = await login_response(client, email, password)
    assert r.status_code == 200, f"sign-in {email}: {r.status_code}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def connect_onboarding_link(ctx: Ctx) -> None:
    import httpx

    async with httpx.AsyncClient(base_url=ctx.api, timeout=60) as c:
        partner = await _login(c, "partner.boi@example.com")
        kitchen = str((await _db("SELECT r.id FROM restaurants r JOIN users u ON u.id = r.owner_id "
                                 "WHERE u.email = 'partner.boi@example.com' ORDER BY r.name LIMIT 1"))[0]["id"])
        await _db("DELETE FROM payout_accounts WHERE payee_id = $1", k=uuid.UUID(kitchen))
        r = await c.post("/api/v1/finance/payout-accounts", headers=partner, json={"payee_type": "restaurant", "restaurant_id": kitchen})
        if r.status_code == 503 and r.json().get("detail", {}).get("code") == "CONNECT_NOT_SET_UP":
            raise AssertionError(r.json()["detail"]["message"])  # says which Dashboard page to finish
        assert r.status_code == 201, f"open account: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body["provider"] == "stripe_connect", f"the US should pay with Stripe Connect, got {body['provider']}"
        assert body["onboarding_url"].startswith("https://connect.stripe.com/"), body["onboarding_url"][:40]
        ext = (await _db("SELECT external_id FROM payout_accounts WHERE id = $1", i=uuid.UUID(body["id"])))[0]["external_id"]
        ctx.created_accounts.append(ext)
        acct = _stripe().Account.retrieve(ext)
        assert acct.get("controller", {}).get("stripe_dashboard", {}).get("type") == "express" or acct.get("type") == "express"
        assert acct["capabilities"].get("transfers") in ("inactive", "pending", "active")
        setup = (await c.get("/api/v1/finance/payout-accounts/me/setup", headers=partner,
                             params={"payee_type": "restaurant", "restaurant_id": kitchen, "refresh": True})).json()
        assert setup["state"] == "in_progress", setup["state"]
        r = await c.get("/api/v1/finance/payout-onboarding", params={"t": "forged.1.x"}, follow_redirects=False)
        assert r.status_code == 302 and "status=expired" in r.headers["location"]


def _test_account(stripe, email: str):  # type: ignore[no-untyped-def]
    """An Express-dashboard account whose requirements the platform supplies, filled with
    Stripe's documented test values so `transfers` turns active without the hosted pages."""
    return stripe.Account.create(
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


async def _poll(fn, seconds: int, what: str):  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        last = await fn()
        if last:
            return last
        await asyncio.sleep(3)
    raise AssertionError(f"timed out after {seconds}s waiting for {what}")


async def connect_payout_transfer(ctx: Ctx) -> None:
    import httpx

    stripe = _stripe()
    acct = _test_account(stripe, f"courier-{uuid.uuid4().hex[:8]}@example.com")
    ctx.created_accounts.append(acct.id)
    rider_id = (await _db("SELECT id FROM users WHERE email = 'rider1.boi@example.com'"))[0]["id"]
    await _db("DELETE FROM payout_accounts WHERE payee_id = $1", k=rider_id)
    await _db("INSERT INTO payout_accounts (id, payee_type, payee_id, provider, external_id, status, country) "
              "VALUES ($1, 'rider', $2, 'stripe_connect', $3, 'pending', 'US')", i=uuid.uuid4(), p=rider_id, e=acct.id)
    ctx.cleanup_sql.append(("DELETE FROM payout_accounts WHERE external_id = $1", {"e": acct.id}))

    async with httpx.AsyncClient(base_url=ctx.api, timeout=60) as c:
        rider = await _login(c, "rider1.boi@example.com")

        async def ready():  # type: ignore[no-untyped-def]
            s = (await c.get("/api/v1/finance/payout-accounts/me/setup", headers=rider,
                             params={"payee_type": "rider", "refresh": True})).json()
            return s if s["state"] == "ready" else None

        await _poll(ready, 120, "the test connected account to have payouts enabled")

        # Money the platform can transfer at once: a test charge that skips the pending balance.
        pi = stripe.PaymentIntent.create(amount=5000, currency="usd", payment_method="pm_card_bypassPending", confirm=True,
                                         automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                                         description="bhojango stripe-e2e: funds for a Connect transfer")
        assert pi.status == "succeeded", pi.status

        # A weekly run for the delivery partner, approved by a finance admin: the transfer.
        start = date(1980, 1, 7) + timedelta(weeks=uuid.uuid4().int % 400)
        run_id, st_id = uuid.uuid4(), uuid.uuid4()
        await _db("INSERT INTO payout_runs (id, country, currency, period_start, period_end, status, totals, created_by) "
                  "VALUES ($1, 'US', 'USD', $2, $3, 'draft', '{}'::jsonb, $4)", i=run_id, s=start, e=start + timedelta(days=7), u=SYSTEM)
        await _db("INSERT INTO payout_statements (id, run_id, payee_type, payee_id, payee_name, currency, amount, summary, lines, status) "
                  "VALUES ($1, $2, 'rider', $3, 'Stripe e2e', 'USD', 1234, '{}'::jsonb, '[]'::jsonb, 'pending')",
                  i=st_id, r=run_id, p=rider_id)
        ctx.cleanup_sql += [("DELETE FROM payout_statements WHERE run_id = $1", {"r": run_id}),
                            ("DELETE FROM payout_runs WHERE id = $1", {"r": run_id})]
        finance = await _login(c, "finance.us@example.com", ADMIN_PW)
        r = await c.post(f"/api/v1/finance/payout-runs/{run_id}/approve", headers=finance)
        assert r.status_code == 200, f"approve: {r.status_code} {r.text[:300]}"
        st = next(s for s in r.json()["statements"] if s["id"] == str(st_id))
        assert st["status"] == "paid" and (st["transfer_id"] or "").startswith("tr_"), f"{st['status']}: {st['error']}"
        tr = stripe.Transfer.retrieve(st["transfer_id"])
        assert tr.destination == acct.id and tr.amount == 1234 and tr.currency == "usd"
        assert tr.metadata["payout_statement_id"] == str(st_id)

        # Reversed in Stripe → the transfer.reversed webhook marks the line reversed (when webhooks reach us).
        stripe.Transfer.create_reversal(tr.id)
        if os.environ.get("STRIPE_E2E_CONNECT_LISTEN", "1") != "0" and shutil.which("stripe"):
            async def reversed_():  # type: ignore[no-untyped-def]
                d = (await c.get(f"/api/v1/finance/payout-runs/{run_id}", headers=finance)).json()
                return next(s for s in d["statements"] if s["id"] == str(st_id))["status"] == "reversed"

            await _poll(reversed_, 90, "transfer.reversed to mark the line reversed")
            got = await _db("SELECT count(*) AS n FROM processed_webhook_events WHERE provider = 'stripe_connect'")
            assert got[0]["n"] >= 1


CASES = [("connect_onboarding_link", connect_onboarding_link), ("connect_payout_transfer", connect_payout_transfer)]


def _listen(api: str) -> subprocess.Popen | None:
    """`stripe listen` for the payout endpoints (key passed by env, never on a printed line)."""
    if os.environ.get("STRIPE_E2E_CONNECT_LISTEN", "1") == "0" or not shutil.which("stripe"):
        print("note: payout webhooks not forwarded by this case (no stripe CLI or STRIPE_E2E_CONNECT_LISTEN=0)")
        return None
    p = subprocess.Popen(
        ["stripe", "listen", "--forward-to", f"{api}/api/v1/finance/stripe/webhook",
         "--forward-connect-to", f"{api}/api/v1/finance/stripe/connect/webhook",
         "--events", "account.updated,account.application.deauthorized,payout.failed,payout.paid,"
                     "transfer.created,transfer.updated,transfer.reversed"],
        env={**os.environ, "STRIPE_API_KEY": os.environ["STRIPE_SECRET_KEY"]},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(8)  # the CLI connects in a few seconds
    return p


async def _cleanup(ctx: Ctx) -> None:
    stripe = _stripe()
    for sql, kw in ctx.cleanup_sql:
        try:
            await _db(sql, **kw)
        except Exception as e:  # noqa: BLE001
            print(f"note: cleanup {sql.split()[2]} failed: {type(e).__name__}")
    for a in ctx.created_accounts:
        try:
            stripe.Account.delete(a)
        except Exception as e:  # noqa: BLE001 - a test account Stripe already removed
            print(f"note: couldn't delete test account: {type(e).__name__}")


async def run(api: str | None = None) -> bool:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        print("FAIL connect payouts: STRIPE_SECRET_KEY must be a test-mode key (sk_test_…)")
        return False
    db = os.environ.get("DATABASE_URL", "")
    if "e2e" not in db.rsplit("/", 1)[-1]:
        print("FAIL connect payouts: DATABASE_URL must be the throwaway e2e database (its name contains 'e2e')")
        return False
    api = (api or os.environ.get("STRIPE_E2E_API_URL") or "http://localhost:8001").rstrip("/")
    import target_guard

    problem = target_guard.api_problem(api)  # never QA's or production's API: this case writes data
    if problem:
        print(f"FAIL connect payouts: refused: {problem}")
        return False
    ctx = Ctx(api)
    listener = _listen(api)
    ok = True
    try:
        for name, case in CASES:
            try:
                await case(ctx)
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001 - every failure is reported, then the next case runs
                ok = False
                print(f"FAIL {name}: {type(e).__name__}: {str(e)[:600]}")
    finally:
        await _cleanup(ctx)
        if listener:
            listener.terminate()
    return ok


if __name__ == "__main__":
    passed = asyncio.run(run())
    print(f"stripe-e2e connect payouts: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)
