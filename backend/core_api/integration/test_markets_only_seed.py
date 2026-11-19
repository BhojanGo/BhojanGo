"""The markets-only seed (tools/seed/markets.py, R19) on a FRESH database, as production runs it.

CI (backend-checks.yml, "Markets-only seed") makes a database of its own, migrates it, runs the
seed twice with production's settings, then runs this file against it with
RUN_MARKETS_ONLY_DB_TESTS=1. Skipped otherwise (the main integration run has the full seed).
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MARKETS_ONLY_DB_TESTS") != "1",
    reason="needs a fresh database with only the markets-only seed (set RUN_MARKETS_ONLY_DB_TESTS=1)",
)


@pytest.fixture
async def db():  # type: ignore[no-untyped-def]
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()


async def scalar(conn, sql: str, **params):  # type: ignore[no-untyped-def]
    return (await conn.execute(text(sql), params)).scalar()


async def test_boise_live_and_india_switched_off(db) -> None:  # type: ignore[no-untyped-def]
    statuses = dict((await db.execute(text("SELECT code, status FROM cities"))).all())
    assert statuses["US-ID-BOI"] == "live"
    assert statuses["IN-TG-HYD"] == "draft"
    assert [c for c, s in statuses.items() if s in ("beta", "live")] == ["US-ID-BOI"]
    countries = dict((await db.execute(text("SELECT code, status FROM countries"))).all())
    assert countries == {"US": "live", "IN": "draft"}
    assert await scalar(db, "SELECT count(*) FROM zones z JOIN cities c ON c.id = z.city_id "
                            "WHERE c.code = 'US-ID-BOI' AND z.status = 'live'") > 0
    assert await scalar(db, "SELECT count(*) FROM zones z JOIN cities c ON c.id = z.city_id "
                            "WHERE c.code = 'IN-TG-HYD' AND z.status <> 'draft'") == 0


async def test_legal_entities_and_rules(db) -> None:  # type: ignore[no-untyped-def]
    names = dict((await db.execute(text("SELECT code, settings->'legal'->>'name' FROM countries"))).all())
    assert names == {"US": "DeepTrics LLC", "IN": "DeepTrics Software Solutions Pvt Ltd"}
    commission = await scalar(db, "SELECT params FROM rules WHERE family = 'commission' AND template = 'percent_by_tier' "
                                  "AND scope_level = 'country' AND scope_id = 'US' AND status = 'published'")
    assert {Decimal(str(v)) for v in commission["tiers"].values()} == {Decimal(15)}
    for family, template in (("business", "commission_tax"), ("business", "payout_tds"), ("business", "payment_fees")):
        assert await scalar(db, "SELECT count(*) FROM rules WHERE family = :f AND template = :t AND scope_id = 'IN'",
                            f=family, t=template) == 1
    assert await scalar(db, "SELECT count(*) FROM rules WHERE scope_level = 'restaurant' OR family = 'promotion'") == 0
    # every rule once, even after two runs
    assert await scalar(db, "SELECT count(*) - count(DISTINCT id) FROM rules") == 0


async def test_no_demo_data_at_all(db) -> None:  # type: ignore[no-untyped-def]
    for table in ("users", "restaurants", "menu_items", "orders", "payout_accounts", "admin_role_assignments"):
        assert await scalar(db, f"SELECT count(*) FROM {table}") == 0, table  # noqa: S608


async def test_legal_documents_are_unpublished_drafts(db) -> None:  # type: ignore[no-untyped-def]
    rows = (await db.execute(text("SELECT country, kind, status, version FROM legal_documents ORDER BY 1, 2"))).all()
    assert {(r[0], r[1]) for r in rows} == {("IN", "privacy"), ("IN", "terms"), ("US", "privacy"), ("US", "terms")}
    assert all(r[2] == "draft" and r[3] is None for r in rows)


async def test_help_articles(db) -> None:  # type: ignore[no-untyped-def]
    assert await scalar(db, "SELECT count(*) FROM help_articles WHERE status = 'published'") > 0


async def test_a_third_run_adds_nothing(db) -> None:  # type: ignore[no-untyped-def]
    """Idempotent: everything is there already (and an admin's change would be kept)."""
    await db.execute(text("UPDATE cities SET status = 'paused' WHERE code = 'US-ID-BOI'"))
    await db.commit()
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "seed"))
    import markets

    try:
        added = await markets.run(os.environ["DATABASE_URL"])
        assert {k: v for k, v in added.items() if k != "help_articles"} == dict.fromkeys(
            ("countries", "regions", "cities", "zones", "rules", "legal_drafts"), 0)
        assert await scalar(db, "SELECT status FROM cities WHERE code = 'US-ID-BOI'") == "paused"
    finally:
        await db.execute(text("UPDATE cities SET status = 'live' WHERE code = 'US-ID-BOI'"))
        await db.commit()
