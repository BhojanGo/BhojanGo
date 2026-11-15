import asyncio
import os
from datetime import date, timedelta

import pytest

OPEN_ALL_DAY_NOTE = "integration tests: open all day"


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    """Login is limited to 10/minute per IP; the suite signs in more than that."""
    from core_api.modules.identity.api.v1.auth import limiter

    limiter.reset()
    yield


@pytest.fixture(autouse=True)
async def _fresh_db_pool():
    """Each test has its own event loop; drop pooled connections bound to it."""
    yield
    from shared.db import engine

    await engine.dispose()


async def open_all_day(restaurant_ids: list | None = None) -> None:
    """Quotes respect real opening hours (P10). So the suite doesn't depend on
    the time it runs, every seeded restaurant gets 24-hour overrides around
    today and cities deliver around the clock."""
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text(
            "UPDATE cities SET service_hours = '{\"open\": \"00:00\", \"close\": \"00:00\"}'::jsonb "
            "WHERE service_hours IS NOT NULL"))
        ids = restaurant_ids or [r for (r,) in (await db.execute(text("SELECT id FROM restaurants"))).all()]
        for rid in ids:
            for offset in range(-2, 4):
                await db.execute(text(
                    "INSERT INTO store_hour_overrides (id, restaurant_id, day, closed, opens, closes, note) "
                    "VALUES (gen_random_uuid(), :r, :d, false, '00:00', '00:00', :n) "
                    "ON CONFLICT (restaurant_id, day) DO UPDATE SET closed = false, opens = '00:00', "
                    "closes = '00:00', note = EXCLUDED.note"),
                    {"r": rid, "d": date.today() + timedelta(days=offset), "n": OPEN_ALL_DAY_NOTE})
        await db.commit()


def target_guard():  # type: ignore[no-untyped-def]
    """tools/target_guard.py (the repo's tools/, also /repo/tools in the test images).
    Missing means we can't tell where we'd write: refuse."""
    import importlib.util
    from pathlib import Path

    for root in Path(__file__).resolve().parents:
        path = root / "tools" / "target_guard.py"
        if path.is_file():
            spec = importlib.util.spec_from_file_location("target_guard", path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod
    pytest.exit("REFUSED: tools/target_guard.py not found, so the test target can't be checked", returncode=3)


def refuse_qa_and_production() -> None:
    """Tests never write to QA or production: this process's APP_ENV and
    RAILWAY_ENVIRONMENT_NAME, and DATABASE_URL's host, must be local."""
    problem = target_guard().process_problem()
    if problem:
        pytest.exit(f"REFUSED (tools/target_guard.py): {problem}", returncode=3)


@pytest.fixture(scope="session", autouse=True)
def _never_qa_or_production():
    if os.environ.get("RUN_MIGRATED_DB_TESTS") == "1":
        refuse_qa_and_production()
    yield


@pytest.fixture(scope="session", autouse=True)
def _restaurants_open_for_tests(_never_qa_or_production):
    if os.environ.get("RUN_MIGRATED_DB_TESTS") != "1":
        yield
        return

    async def go() -> None:
        from shared.db import engine

        await open_all_day()
        await engine.dispose()  # pooled connections belong to this event loop

    asyncio.run(go())
    yield
