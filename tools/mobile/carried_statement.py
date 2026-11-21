"""Kitchen statements below zero on THIS machine's stack (R23, R24), so the partner app's flow
apps/partner/.maestro/stack/05-payouts-carried.yaml can screenshot Payouts with a week below zero on
top of a balance carried in (both lines: "This week came to ₹30.00 below zero." and "Still ₹50.00
below zero from earlier weeks · carried to next week.") and the next week's "Carried from last week".

Runs on the host (tools/mobile/stack-screens.sh), written with psql in the stack's postgres container
as payout runs leave them: four weeks ago Spice Route Kitchen's statement comes to -₹50.00 (refunds
outweighed its sales) and admin approves it (nothing is sent: carried); three weeks ago its own week
is -₹30.00 on top of the -₹50.00 carried in (-₹80.00, carried again; the earlier statement names it in
carried_to) and admin approves it; finance prepares the week after it through the API (it carries the
-₹80.00), the kitchen sets up payouts and admin approves. Last week is left to the payout scheduler, which may already have drafted it. Idempotent: a week that already has a run is left alone. Never against QA or
production (tools/target_guard.py).
    python tools/mobile/carried_statement.py [core url, default http://localhost:8001]
"""
import os
import shlex
import subprocess
import sys

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from target_guard import ensure_safe_api  # noqa: E402
from totp_signin import finish  # noqa: E402

CORE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001").rstrip("/") + "/api/v1"
ensure_safe_api(CORE)
PSQL = shlex.split(os.environ.get("PSQL", f"docker compose -f {ROOT}/infra/docker/compose.yaml exec -T postgres psql -U bhojango -d bhojango"))
ADMIN_PW = "BhojanGoAdmin1"


def sign_in(c: httpx.Client, email: str, pw: str) -> dict:
    body = c.post(f"{CORE}/auth/login", json={"email": email, "password": pw}).json()
    tokens = finish(lambda path, data: c.post(f"{CORE}{path}", json=data).json(), email, body)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def psql(sql: str) -> str:
    return subprocess.run([*PSQL, "-v", "ON_ERROR_STOP=1", "-tAc", sql], check=True, capture_output=True, text=True).stdout.strip()


with httpx.Client(timeout=60) as c:
    finance, admin = sign_in(c, "finance.in@example.com", ADMIN_PW), sign_in(c, "admin@example.com", ADMIN_PW)
    partner = sign_in(c, "partner.hyd@example.com", "BhojanGo123")
    kitchen = next(r["id"] for r in c.get(f"{CORE}/restaurants", params={"limit": 50}).json()["items"]
                   if r["name"] == "Spice Route Kitchen")
    last, before, earlier = c.get(f"{CORE}/finance/payout-weeks", headers=finance, params={"country": "IN"}).json()["weeks"][1:4]

    def runs_by_week() -> dict:
        return {r["period_start"]: r for r in c.get(f"{CORE}/finance/payout-runs", headers=finance, params={"country": "IN"}).json()}

    def week_below_zero(wk: dict, amount: int, carried_in: int, weeks: int, summary: str) -> None:
        """A run with Spice Route Kitchen's statement below zero, as a payout run leaves it; it carries
        in the kitchen's earlier statement still below zero (carried_to names it, as create_run does)."""
        psql(f"""WITH r AS (INSERT INTO payout_runs (id, country, currency, period_start, period_end, status, totals, created_by)
                 VALUES (gen_random_uuid(), 'IN', 'INR', '{wk["start"]}', '{wk["end"]}', 'draft', '{{"orders": 2}}',
                         '00000000-0000-0000-0000-000000000000') RETURNING id),
                 s AS (INSERT INTO payout_statements (id, run_id, payee_type, payee_id, payee_name, currency, amount, summary, lines,
                                                      status, attempts, carried_in, negative_weeks, negative_since)
                 SELECT gen_random_uuid(), r.id, 'restaurant', '{kitchen}', 'Spice Route Kitchen', 'INR', {amount},
                        '{summary}', '[]', 'pending', 0, {carried_in}, {weeks}, '{earlier["start"]}' FROM r RETURNING id)
                 UPDATE payout_statements SET carried_to = (SELECT id FROM s)
                  WHERE payee_type = 'restaurant' AND payee_id = '{kitchen}' AND amount < 0 AND carried_to IS NULL
                    AND id <> (SELECT id FROM s)""")

    def approve(wk: dict, what: str) -> None:
        run = runs_by_week()[wk["start"]]
        if run["status"] == "draft":
            r = c.post(f"{CORE}/finance/payout-runs/{run['id']}/approve", headers=admin)
            print(what, "approved:", r.status_code, r.json().get("status"))

    runs = runs_by_week()
    if earlier["start"] not in runs:  # four weeks ago: -50.00, nothing carried in
        week_below_zero(earlier, -5000, 0, 1, '{"orders": 2, "net": "-50.00"}')
    approve(earlier, "week below zero")
    if before["start"] not in runs:  # three weeks ago: its own week -30.00 on top of the -50.00 carried in
        week_below_zero(before, -8000, -5000, 2,
                        '{"orders": 2, "net": "-30.00", "carried_from_last_week": "-50.00", "amount": "-80.00"}')
    approve(before, "week below zero on a carried balance")
    runs = runs_by_week()

    print("payout account:", c.post(f"{CORE}/finance/payout-accounts", headers=partner,
                                     json={"payee_type": "restaurant", "restaurant_id": kitchen}).status_code)
    if last["start"] not in runs:
        r = c.post(f"{CORE}/finance/payout-runs", headers=finance,
                   json={"country": "IN", "period_start": last["start"], "period_end": last["end"]})
        print("next week prepared:", r.status_code, r.json().get("totals"))
        r = c.post(f"{CORE}/finance/payout-runs/{r.json()['id']}/approve", headers=admin)
        mine = next(s for s in r.json()["statements"] if s["payee_id"] == kitchen)
        print("next week approved:", r.status_code, "kitchen:", mine["amount"], mine["status"], "carried in", mine["carried_in"])
