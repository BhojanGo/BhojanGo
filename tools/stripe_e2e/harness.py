"""Stripe test-mode end-to-end harness (started by tools/stripe_e2e/run.sh).

Discovers every ``test_*.py`` next to this file (or the files named on the
command line) and runs each module-level ``case_<name>(h)`` function in file
and definition order, with ``h`` an :class:`H`: the throwaway core-api's URL,
signed-in API sessions, the Stripe SDK (test key), SQL on the throwaway database
and polling helpers. A case passes by returning, fails by raising, and is
skipped with ``raise Skip("why")``. Prints PASS/FAIL/SKIP per case and one line
``stripe-e2e: RESULT passed=N failed=N skipped=N``; exits 1 if any case failed.

Adding cases (e.g. the Connect workstream's ``test_payouts.py``): a new file
with ``case_*`` functions; nothing to register. Keys are never printed.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import time
import traceback
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))  # tools/: totp_signin.py

CUSTOMER_PASSWORD, ADMIN_PASSWORD = "BhojanGo123", "BhojanGoAdmin1"  # the base seed's fixed test passwords
SECRET = re.compile(r"(sk|rk|pk)_(test|live)_[A-Za-z0-9]+|whsec_[A-Za-z0-9]+|pi_[A-Za-z0-9]+_secret_[A-Za-z0-9]+")


def redact(text: str) -> str:
    return SECRET.sub(lambda m: m.group(0).split("_")[0] + "_***", text)


class Skip(Exception):
    """The case can't run here (said why); not a failure."""


class Api:
    """One person's HTTP session against the throwaway core-api."""

    def __init__(self, base: str, email: str, password: str) -> None:
        self.base = base
        self.client = httpx.Client(timeout=60)
        r = self._login(email, password)
        if r.json().get("mfa_required"):  # an admin: the second step (tools/totp_signin.py, the seed's key)
            from totp_signin import next_code

            r = self.client.post(f"{base}/api/v1/auth/mfa/verify", json={"mfa_token": r.json()["mfa_token"], "code": next_code(email)})
            assert r.status_code == 200, f"admin second step: {r.status_code} {r.text[:200]}"
        self.user = r.json()["user"]
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _login(self, email: str, password: str) -> httpx.Response:
        for _ in range(20):
            r = self.client.post(f"{self.base}/api/v1/auth/login", json={"email": email, "password": password})
            if r.status_code != 429:
                break
            time.sleep(6)  # login is limited per minute
        assert r.status_code == 200, f"sign-in {email}: {r.status_code} {r.text[:200]}"
        return r

    def call(self, method: str, path: str, expect: int | tuple[int, ...] | None = None, **kw: Any) -> Any:
        headers = {**self.headers, **kw.pop("headers", {})}
        r = self.client.request(method, f"{self.base}/api/v1{path}", headers=headers, **kw)
        if expect is not None:
            ok = (expect,) if isinstance(expect, int) else expect
            assert r.status_code in ok, f"{method} {path}: {r.status_code} {redact(r.text[:400])}"
        try:
            return r.json()
        except ValueError:
            return r.text


class H:
    """What a case gets."""

    def __init__(self) -> None:
        self.core = os.environ["STRIPE_E2E_CORE"]
        self.psql_url = os.environ["STRIPE_E2E_PSQL"]
        self.work = Path(os.environ.get("STRIPE_E2E_WORK", "/tmp"))
        self.publishable_key = os.environ["STRIPE_PUBLISHABLE_KEY"]
        self._sessions: dict[str, Api] = {}
        self.state: dict[str, Any] = {}  # what one case leaves for a later one (e.g. a paid order to refund)
        import stripe

        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        self.stripe = stripe

    def api(self, email: str) -> Api:
        """A signed-in session (seed users; admins answer the two-step sign-in)."""
        if email not in self._sessions:
            admin = not re.match(r"^(customer|partner|rider)", email)
            self._sessions[email] = Api(self.core, email, ADMIN_PASSWORD if admin else CUSTOMER_PASSWORD)
        return self._sessions[email]

    def sql(self, query: str) -> list[list[str]]:
        """Read the throwaway database (psql, tab-separated rows)."""
        out = subprocess.run(["psql", self.psql_url, "-qAtX", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", query],
                             capture_output=True, text=True, timeout=60, check=True).stdout
        return [line.split("\t") for line in out.splitlines() if line]

    @staticmethod
    def wait(pred: Callable[[], Any], timeout: float = 60, every: float = 1.0, what: str = "condition") -> Any:
        end = time.time() + timeout
        while time.time() < end:
            v = pred()
            if v:
                return v
            time.sleep(every)
        raise AssertionError(f"timed out after {timeout:.0f}s waiting for {what}")

    @staticmethod
    def idem() -> dict[str, str]:
        return {"X-Idempotency-Key": str(uuid.uuid4())}

    # ── shared order steps (US: Boise) ──────────────────────────────────────
    def boise_quote(self, customer: Api, items: dict[str, int] | None = None) -> tuple[dict, dict, dict, list[dict]]:
        """(restaurant, address, quote, cart) for a Boise order from the seed."""
        rest = next(r for r in customer.call("GET", "/restaurants", 200, params={"limit": 50})["items"] if r["name"] == "Boise Bowl Co.")
        menu = customer.call("GET", f"/restaurants/{rest['id']}/menu", 200)
        ids = {i["name"]: i["id"] for c in menu.get("categories", []) for i in c.get("items", [])}
        cart = [{"menu_item_id": ids[name], "quantity": n} for name, n in (items or {"Teriyaki Chicken Bowl": 2}).items()]
        address = customer.call("GET", "/me/addresses", 200)[0]
        q = customer.call("POST", "/pricing/quote", 200, json={"restaurant_id": rest["id"], "items": cart,
                                                               "deliver_to": {"address_id": address["id"]}, "tip": "2"})
        return rest, address, q, cart

    def place(self, customer: Api, rest: dict, address: dict, q: dict, cart: list[dict]) -> dict:
        return customer.call("POST", "/orders", 201, headers=self.idem(), json={
            "restaurant_id": rest["id"], "items": cart, "payment_method": "card", "quote_token": q["token"],
            "delivery_address": {"street": address.get("street") or "1510 N 13th St", "city": "Boise", "state": "ID",
                                 "zip": address.get("postal_code") or "83702", "country": "US"}})

    def initiate(self, customer: Api, order_id: str) -> dict:
        init = customer.call("POST", "/payments/initiate", 201, json={"order_id": order_id, "payment_method_type": "card"})
        assert init["provider"] == "stripe", f"expected Stripe, got {init['provider']}"
        return init

    def pay_status(self, customer: Api, order_id: str) -> dict:
        return customer.call("GET", f"/payments/orders/{order_id}/status", 200)

    def wait_payment(self, customer: Api, order_id: str, want: str, timeout: float = 90) -> dict:
        """Until the webhook (via the Stripe CLI) has set the payment's status."""
        return self.wait(lambda: (s := self.pay_status(customer, order_id))["payment_status"] == want and s,
                         timeout, 2, f"payment_status={want} (webhook)")


def discover(names: list[str]) -> list[tuple[str, Callable[[H], None]]]:
    files = [HERE / n for n in names] if names else sorted(HERE.glob("test_*.py"))
    cases = []
    for f in files:
        spec = importlib.util.spec_from_file_location(f"stripe_e2e_{f.stem}", f)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name, fn in vars(mod).items():  # definition order
            if name.startswith("case_") and callable(fn):
                cases.append((f"{f.stem}.{name[5:]}", fn))
    return cases


def main(argv: list[str]) -> int:
    h = H()
    passed = failed = skipped = 0
    cases = discover(argv)
    print(f"stripe-e2e: {len(cases)} cases")
    for name, fn in cases:
        t0 = time.time()
        try:
            fn(h)
        except Skip as e:
            skipped += 1
            print(f"SKIP {name}: {redact(str(e))}", flush=True)
            continue
        except Exception as e:  # noqa: BLE001 (a case's failure, reported and counted)
            failed += 1
            print(f"FAIL {name} ({time.time() - t0:.0f}s): {redact(f'{type(e).__name__}: {e}')}", flush=True)
            print(redact("".join(traceback.format_exc().splitlines(True)[-6:])), flush=True)
            continue
        passed += 1
        print(f"PASS {name} ({time.time() - t0:.0f}s)", flush=True)
    print(f"stripe-e2e: RESULT {'PASS' if failed == 0 else 'FAIL'} passed={passed} failed={failed} skipped={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
