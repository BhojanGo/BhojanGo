"""Tests never write to QA or production, nor to the dev/demo database (R42).

Everything that creates data through the APIs or the database (the backend
integration and G1 suites, the Playwright and Maestro runs, k6, the soak, the
Railway checks) calls this first and refuses to run, with a clear message and a
non-zero exit, when its target is an environment named qa or production. Tests
run locally (make dev, make ci) and in CI; QA only gets read-only checks and the
demo data (tools/seed/demo.py).

How the target is known:
- an API: its public GET /health reports `environment` (APP_ENV). A target that
  doesn't say is refused unless it's on this machine or a compose network.
- this process (a conftest that opens the database): APP_ENV and
  RAILWAY_ENVIRONMENT_NAME, and DATABASE_URL's host must be local (loopback or
  a compose service name; any dotted host such as *.railway.internal is remote).
- R42: the database itself must be a throwaway test one, its name containing
  "test" (tools/test_db.py makes bhojango_test_<id> per run and drops it; CI's
  stacks use bhojango_test, bhojango_e2e_test, ...). The dev/demo database
  (bhojango) is refused. An API says so in /health: `test_database: true`.

Standard library only: the Playwright image runs it with a bare Python.

    python tools/target_guard.py api <core url> [<url> ...]   # exit 3 = refused
    python tools/target_guard.py process                      # this process's env and DATABASE_URL
"""
from __future__ import annotations

import ipaddress
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping

PROTECTED = frozenset({"qa", "production", "prod"})
REFUSED_EXIT = 3


class Refused(SystemExit):
    """The target is QA or production (or can't be told apart from them)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(REFUSED_EXIT)

    def __str__(self) -> str:
        return self.reason


def protected(name: str | None) -> bool:
    return (name or "").strip().lower() in PROTECTED


def local_host(host: str | None) -> bool:
    """Loopback, or a single-label name (a compose service such as `postgres` or `core-api`)."""
    if not host:
        return True  # a Unix socket
    host = host.strip("[]").lower()
    if host == "localhost" or host == "host.docker.internal":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return "." not in host


def database_name(url: str) -> str:
    return urllib.parse.urlsplit(url.replace("+asyncpg", "")).path.lstrip("/").lower()


def test_database(name: str) -> bool:
    """A throwaway test database: its name has "test" in it (the same rule as Settings.test_database)."""
    return "test" in name.lower()


NOT_A_TEST_DB = ("tests only write to a throwaway test database (a name with 'test' in it; "
                 "run them through tools/test_db.py), never the dev/demo database")


def process_problem(env: Mapping[str, str] | None = None) -> str | None:
    """Why this process must not write test data, or None."""
    env = os.environ if env is None else env
    for var in ("APP_ENV", "RAILWAY_ENVIRONMENT_NAME"):
        if protected(env.get(var)):
            return f"{var}={env.get(var)!r}: tests never write to QA or production"
    url = env.get("DATABASE_URL", "")
    if url:
        host = urllib.parse.urlsplit(url.replace("+asyncpg", "")).hostname
        if not local_host(host):
            return (f"DATABASE_URL points at {host!r}, not a local or compose database: "
                    "tests never write to a hosted database")
        name = database_name(url)
        if not test_database(name):
            return f"DATABASE_URL's database is {name!r}: {NOT_A_TEST_DB}"
    return None


Fetch = Callable[[str], dict]


def _fetch_health(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310 (http(s) only, checked below)
        return json.loads(r.read() or b"{}")


def api_problem(base_url: str, fetch: Fetch = _fetch_health) -> str | None:
    """Why an API must not get test data, or None. ``base_url`` may end in /api/v1."""
    base = base_url.rstrip("/")
    if base.endswith("/api/v1"):
        base = base[: -len("/api/v1")]
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return f"{base_url!r} isn't an http(s) URL"
    try:
        health = fetch(f"{base}/health")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return f"couldn't read {base}/health ({e}); refusing rather than guessing the environment"
    env = health.get("environment") if isinstance(health, dict) else None
    if protected(env):
        return f"{base} is the {env!r} environment: tests never write to QA or production"
    if not env and not local_host(parts.hostname):
        return f"{base}/health doesn't report its environment; refusing a hosted target"
    if health.get("test_database") is not True:
        return f"{base} doesn't run on a test database (/health test_database is not true): {NOT_A_TEST_DB}"
    return None


def _refuse(reason: str) -> None:
    print(f"REFUSED (tools/target_guard.py): {reason}", file=sys.stderr, flush=True)
    raise Refused(reason)


def ensure_local_process(env: Mapping[str, str] | None = None) -> None:
    if (p := process_problem(env)) is not None:
        _refuse(p)


def ensure_safe_api(*base_urls: str, fetch: Fetch = _fetch_health) -> None:
    for url in base_urls:
        if url and (p := api_problem(url, fetch)) is not None:
            _refuse(p)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "api":
        ensure_safe_api(*argv[1:])
    elif argv == ["process"]:
        ensure_local_process()
    else:
        print(__doc__, file=sys.stderr)
        return 2
    print("target_guard: ok (a local test database; not QA, production or the dev/demo database)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
