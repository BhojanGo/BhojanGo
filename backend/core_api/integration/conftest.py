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


@pytest.fixture(scope="session", autouse=True)
def _restaurants_open_for_tests():
    if os.environ.get("RUN_MIGRATED_DB_TESTS") != "1":
        yield
        return

    async def go() -> None:
        from shared.db import engine

        await open_all_day()
        await engine.dispose()  # pooled connections belong to this event loop

    asyncio.run(go())
    yield
