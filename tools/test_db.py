"""R42: run database tests on a database of their own, created for the run and dropped after it.

Integration tests never touch the dev/demo database (bhojango): this makes bhojango_test_<id> on the same Postgres
server, sets it up like a new one (infra/docker/db/init.sql, migrations, the seed), runs the command with
DATABASE_URL pointing at it and Redis on a database index of its own, then drops it, whatever the result.
tools/target_guard.py refuses a test run on any database whose name hasn't got "test" in it.

    cd backend && DATABASE_URL=postgresql+asyncpg://bhojango:bhojango_dev@localhost:15432/bhojango \\
        REDIS_URL=redis://localhost:16379/0 uv run python ../tools/test_db.py -- python -m pytest core_api/integration

--keep leaves the database (to look at a failure); --no-seed skips the seed. --prove-untouched counts what tests
could write in the server's own database (DATABASE_URL's: the dev/demo one) before and after, prints both and fails
the run if anything changed. Exit code: the command's (or 4 when the dev database changed).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import urllib.parse
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
INIT_SQL = ROOT / "infra" / "docker" / "db" / "init.sql"
TEST_REDIS_DB = "15"  # the dev stack's services use 0


def with_database(url: str, name: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parts._replace(path="/" + name))


def database_label(url: str) -> str:
    return urllib.parse.urlsplit(url).path.lstrip("/")


def plain(url: str) -> str:
    return url.replace("+asyncpg", "")


async def _admin(url: str, sql: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(plain(with_database(url, "postgres")), ssl=False)  # local only
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _init(url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(plain(url), ssl=False)  # a local test server
    try:
        await conn.execute(INIT_SQL.read_text(encoding="utf-8"))
    finally:
        await conn.close()


# What a test run creates (R42 brief: orders, payout runs, disputes, balances), counted in the dev database.
UNTOUCHED = {
    "orders": "SELECT count(*) FROM orders",
    "refunds": "SELECT count(*) FROM refunds",
    "payout runs": "SELECT count(*) FROM payout_runs",
    "payout statements": "SELECT count(*) FROM payout_statements",
    "balances (statements carried below zero)": "SELECT count(*) FROM payout_statements WHERE amount < 0",
    "disputes": "SELECT count(*) FROM payment_disputes",
    "support tickets": "SELECT count(*) FROM support_tickets",
    "users": "SELECT count(*) FROM users",
}


async def _counts(url: str) -> dict[str, int]:
    import asyncpg

    conn = await asyncpg.connect(plain(url), ssl=False)  # a local test server
    try:
        return {k: int(await conn.fetchval(q)) for k, q in UNTOUCHED.items()}
    finally:
        await conn.close()


def run(cmd: list[str], env: dict[str, str]) -> int:
    print("test_db:", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=BACKEND, env=env)


def main(argv: list[str]) -> int:
    keep, seed, prove = "--keep" in argv, "--no-seed" not in argv, "--prove-untouched" in argv
    if "--" not in argv:
        print(__doc__, file=sys.stderr)
        return 2
    command = argv[argv.index("--") + 1:]
    if command and command[0] in ("python", "python3"):
        command[0] = sys.executable  # this venv's (Windows looks next to the parent process first)
    base = os.environ.get("DATABASE_URL", "")
    if not base.startswith("postgresql"):
        print("test_db: DATABASE_URL (the server to make the test database on) is not set", file=sys.stderr)
        return 2
    name = f"bhojango_test_{uuid.uuid4().hex[:10]}"
    url = with_database(base, name)
    env = {**os.environ, "DATABASE_URL": url, "RUN_MIGRATED_DB_TESTS": os.environ.get("RUN_MIGRATED_DB_TESTS", "1")}
    if env.get("REDIS_URL"):
        r = urllib.parse.urlsplit(env["REDIS_URL"])
        env["REDIS_URL"] = urllib.parse.urlunsplit(r._replace(path="/" + TEST_REDIS_DB))
    before = asyncio.run(_counts(base)) if prove else {}
    print(f"test_db: creating {name}", flush=True)
    asyncio.run(_admin(base, f'CREATE DATABASE "{name}"'))
    status = 1
    try:
        asyncio.run(_init(url))
        py = [sys.executable]
        steps = [py + ["-m", "alembic", "upgrade", "head"]] + ([py + [str(ROOT / "tools" / "seed" / "seed.py")]] if seed else [])
        for step in steps:
            if (status := run(step, {**env, "PYTHONIOENCODING": "utf-8"})) != 0:
                print(f"test_db: setup step failed ({status})", file=sys.stderr)
                return status
        status = run(command, env)
        if prove:
            after = asyncio.run(_counts(base))
            dev = database_label(base)
            print(f"test_db: the dev database ({dev}) before -> after the run:", flush=True)
            for k in UNTOUCHED:
                print(f"    {k:<42} {before[k]:>8} -> {after[k]:>8}   new: {after[k] - before[k]}", flush=True)
            if after != before:
                print(f"test_db: FAIL: the run changed the dev database ({dev})", file=sys.stderr, flush=True)
                return status or 4
            print(f"test_db: the dev database ({dev}) is untouched", flush=True)
        return status
    finally:
        if keep:
            print(f"test_db: kept {name} (--keep)", flush=True)
        else:
            asyncio.run(_admin(base, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            print(f"test_db: dropped {name}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
