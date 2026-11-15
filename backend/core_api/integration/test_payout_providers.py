"""Payout providers per country from Markets (countries.payout_provider) on a
migrated, seeded Postgres: the 0027 backfill, choosing it in Markets, a country
without one can't open, and payouts use the country's choice."""
import importlib.util
import os
import random
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from core_api.integration.test_orders_flow import login

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


def migration():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0027_country_payout_provider.py"
    spec = importlib.util.spec_from_file_location("m0027", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


async def test_migration_backfills_what_the_code_used_to_pick() -> None:
    """IN -> razorpay_route, US -> stripe_connect, any other country -> none (the column default)."""
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        default = (await db.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'countries' AND column_name = 'payout_provider'"))).scalar_one()
        assert "none" in default
        await db.execute(text("UPDATE countries SET payout_provider = DEFAULT"))  # as just after add_column
        for sql in migration().BACKFILL:
            await db.execute(text(sql))
        got = dict((await db.execute(text("SELECT code, payout_provider FROM countries"))).all())
        assert got["IN"] == "razorpay_route" and got["US"] == "stripe_connect", got
        assert all(v == "none" for k, v in got.items() if k not in ("IN", "US")), got
        await db.rollback()  # leave the seeded values as they were


async def test_seed_and_markets_expose_the_provider(client: AsyncClient) -> None:
    sup = await login(client, "admin@example.com", ADMIN)
    got = {k["code"]: k["payout_provider"] for k in (await client.get("/api/v1/markets", headers=sup)).json()}
    assert got["IN"] == "razorpay_route" and got["US"] == "stripe_connect", got


async def _new_country(client: AsyncClient, sup: dict, **extra) -> str:  # type: ignore[no-untyped-def]
    for _ in range(20):
        code = "Z" + random.choice("ABCDEFGHJKLMNPQRSTUVWXY")
        r = await client.post("/api/v1/markets/countries", headers=sup, json={
            "code": code, "name": f"Payland {code}", "currency": "EUR", "locales": ["en-GB"], "timezone": "UTC",
            "phone_code": "+997", "payment_providers": ["stripe"], "tax_regime": "gst", **extra})
        if r.status_code == 201:
            return code
        assert r.status_code == 409, r.text
    raise AssertionError("no free test country code")


async def test_a_country_without_a_payout_provider_cannot_open(client: AsyncClient) -> None:
    sup = await login(client, "admin@example.com", ADMIN)
    code = await _new_country(client, sup)  # no payout provider given: none
    country = next(k for k in (await client.get("/api/v1/markets", headers=sup)).json() if k["code"] == code)
    assert country["payout_provider"] == "none" and country["status"] == "draft"

    # announcing it is fine; opening it isn't
    assert (await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"status": "soon"})).status_code == 200
    for status in ("beta", "live"):
        r = await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"status": status})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "MARKET_RULE", r.text
        assert "no payout provider" in r.json()["detail"]["message"]
    # a city in it lists the missing provider in its launch checklist
    region = f"{code}-N"
    r = await client.post(f"/api/v1/markets/countries/{code}/regions", headers=sup, json={"code": region, "name": "North"})
    assert r.status_code == 201, r.text
    r = await client.post(f"/api/v1/markets/regions/{region}/cities", headers=sup,
                          json={"code": f"{region}-PAY", "name": "Paytown", "center_lat": 10.0, "center_lng": 10.0})
    assert r.status_code == 201, r.text
    city = (await client.get(f"/api/v1/markets/cities/{region}-PAY", headers=sup)).json()
    assert city["launch_checklist"]["payouts_set"] is False

    # with a provider it opens (the fake, outside production); then it can't drop back to none while open
    r = await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"payout_provider": "fake"})
    assert r.status_code == 200 and r.json()["payout_provider"] == "fake"
    city = (await client.get(f"/api/v1/markets/cities/{region}-PAY", headers=sup)).json()
    assert city["launch_checklist"]["payouts_set"] is True
    r = await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"status": "live"})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"payout_provider": "none"})
    assert r.status_code == 409 and "no payout provider" in r.text
    r = await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"payout_provider": "paypal"})
    assert r.status_code == 422
    # back to a draft so nothing else sees the test country open
    assert (await client.patch(f"/api/v1/markets/countries/{code}", headers=sup, json={"status": "draft"})).status_code == 200


async def test_production_refuses_the_fake_provider(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from core_api.modules.markets.service import markets as M

    sup = await login(client, "admin@example.com", ADMIN)
    monkeypatch.setattr(M, "_production", lambda: True)
    r = await client.post("/api/v1/markets/countries", headers=sup, json={
        "code": "ZZ", "name": "Fakeland", "currency": "EUR", "locales": ["en-GB"], "timezone": "UTC",
        "phone_code": "+997", "payment_providers": ["stripe"], "tax_regime": "gst", "payout_provider": "fake"})
    assert r.status_code == 409 and "fake payout provider" in r.text, r.text
    r = await client.patch("/api/v1/markets/countries/US", headers=sup, json={"payout_provider": "fake"})
    assert r.status_code == 409 and "fake payout provider" in r.text, r.text


def _settings(mode: str, keys: bool):  # type: ignore[no-untyped-def]
    return SimpleNamespace(
        is_production=False, providers=SimpleNamespace(PAYOUT_PROVIDER=mode),
        payments=SimpleNamespace(STRIPE_SECRET_KEY="sk_test_x" if keys else "", RAZORPAY_KEY_ID="rzp_x" if keys else "",
                                 RAZORPAY_KEY_SECRET="s" if keys else ""))


async def test_payouts_use_the_countrys_provider(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from core_api.modules.finance.service import providers as P
    from shared.db import AsyncSessionLocal

    sup = await login(client, "admin@example.com", ADMIN)
    fake_code = await _new_country(client, sup, payout_provider="fake")
    none_code = await _new_country(client, sup)
    # a deployment with live keys: each country gets its own provider from Markets (nothing is called)
    monkeypatch.setattr(P, "get_settings", lambda: _settings("live", keys=True))
    async with AsyncSessionLocal() as db:
        assert (await P.country_payout_provider(db, "IN")).name == "razorpay_route"
        assert (await P.country_payout_provider(db, "US")).name == "stripe_connect"
        assert (await P.country_payout_provider(db, fake_code)).name == "fake"
        with pytest.raises(P.NoPayoutProvider, match="Markets"):
            await P.country_payout_provider(db, none_code)
    # CI and QA without keys (PAYOUT_PROVIDER=auto): the fake stands in for the country's provider
    monkeypatch.setattr(P, "get_settings", lambda: _settings("auto", keys=False))
    async with AsyncSessionLocal() as db:
        assert (await P.country_payout_provider(db, "IN")).name == "fake"
    monkeypatch.undo()

    # a payee in a country with no payout provider can't open an account: a clear 409
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE countries SET payout_provider = 'none' WHERE code = 'IN'"))
        await db.commit()
    try:
        rider = await login(client, "rider1.hyd@example.com")
        r = await client.post("/api/v1/finance/payout-accounts", headers=rider, json={"payee_type": "rider"})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "FINANCE_RULE", r.text
        assert "payout provider" in r.json()["detail"]["message"]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE countries SET payout_provider = 'razorpay_route' WHERE code = 'IN'"))
            await db.commit()
