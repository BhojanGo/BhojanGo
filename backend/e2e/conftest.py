"""Black-box tests against a running stack (`make ci-e2e`, or `make dev`).

They talk to the services over HTTP like the apps do. Only two things go
around the API, both standing in for the system rather than a person:
- the stack is opened around the clock (city and restaurant hours) so the
  tests don't depend on when they run;
- the weekly payout job is run as the scheduler would on payout day.

URLs come from E2E_* variables; without E2E_CORE_API the tests are skipped.
"""
import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest

CORE = os.environ.get("E2E_CORE_API", "")
RT = os.environ.get("E2E_REALTIME", "http://localhost:8004")
WK = os.environ.get("E2E_WORKER", "http://localhost:8006")
# Empty E2E_MAILPIT: no mail catcher (hosted QA logs email); the email check
# reads the notifications table instead.
MAIL = os.environ.get("E2E_MAILPIT", "http://localhost:8025")
PASSWORD, ADMIN_PASSWORD = "BhojanGo123", "BhojanGoAdmin1"
# Hosted QA seeds random passwords (tools/seed: SEED_PASSWORDS=random); point
# E2E_LOGINS_FILE at the logins file it wrote (outside the repo).
LOGINS: dict[str, str] = {}
if os.environ.get("E2E_LOGINS_FILE"):
    with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as f:
        LOGINS = {row[2]: row[3] for row in (line.rstrip("\n").split("\t") for line in f) if len(row) == 4}

pytestmark = pytest.mark.skipif(not CORE, reason="needs a running stack (set E2E_CORE_API)")


class Api:
    """One person's HTTP session against core_api, realtime and worker."""

    def __init__(self, email: str, password: str = PASSWORD) -> None:
        password = LOGINS.get(email, password)
        self.client = httpx.Client(timeout=30)
        for _ in range(30):
            r = self.client.post(f"{CORE}/api/v1/auth/login", json={"email": email, "password": password})
            if r.status_code != 429:
                break
            time.sleep(5)  # login is limited to 10/minute
        assert r.status_code == 200, r.text
        self.user = r.json()["user"]
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _do(self, base: str, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = {**self.headers, **kw.pop("headers", {})}
        for attempt in range(3):  # a reused keep-alive connection can be closed by the server
            try:
                return self.client.request(method, f"{base}/api/v1{path}", headers=headers, **kw)
            except httpx.RemoteProtocolError:
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    def core(self, method: str, path: str, **kw: Any) -> httpx.Response:
        return self._do(CORE, method, path, **kw)

    def rt(self, method: str, path: str, **kw: Any) -> httpx.Response:
        return self._do(RT, method, path, **kw)

    def wk(self, method: str, path: str, **kw: Any) -> httpx.Response:
        return self._do(WK, method, path, **kw)


def wait_for(pred: Callable[[], Any], timeout: float = 45, every: float = 0.5) -> Any:
    end = time.time() + timeout
    while time.time() < end:
        value = pred()
        if value:
            return value
        time.sleep(every)
    return None


def idem() -> dict[str, str]:
    return {"X-Idempotency-Key": str(uuid.uuid4())}


@pytest.fixture(scope="session", autouse=True)
def open_around_the_clock() -> None:
    """City and restaurant hours open all day (what core_api's integration suite does)."""
    if not CORE:
        return
    import asyncio

    from core_api.integration.conftest import open_all_day
    from shared.db import engine

    async def go() -> None:
        await open_all_day()
        await engine.dispose()

    asyncio.run(go())
