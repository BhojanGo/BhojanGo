"""Deliver with BhojanGo (R8 F8) on Postgres: GET /delivery/terms gives each live
city's pay from its own rules and its country's requirements from Markets, and a
change in Markets shows up on the page.

    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration/test_deliver.py -v
"""
import os
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.modules.identity.tests.signin import login_response

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

ADMIN_PW = "BhojanGoAdmin1"


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def _admin(client: AsyncClient) -> dict:
    r = await login_response(client, "admin@example.com", ADMIN_PW)  # with the admin's second step
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_hyderabad_terms_come_from_its_rules(client: AsyncClient) -> None:
    r = await client.get("/api/v1/delivery/terms", params={"city": "IN-TG-HYD"})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["city"]["name"] == "Hyderabad" and t["country"] == "IN" and t["currency"] == "INR" and t["phone_code"] == "+91"
    ex = t["example"]  # R30: a trip pays its delivery fee, seed ₹20 + ₹6 per km, at 3 km; no waiting pay
    assert Decimal(ex["distance"]) == 3 and Decimal(ex["base"]) == 20 and Decimal(ex["per_unit"]) == 6
    assert Decimal(ex["total"]) == 38 and Decimal(ex["distance_pay"]) == 18 and ex["free_wait_minutes"] == 0
    assert Decimal(ex["per_wait_minute"]) == 0
    assert t["hourly_floor"] is None and t["batch_bonus"] is None and t["tips_percent"] == 100
    assert t["pay_schedule"] == {"frequency": "weekly", "day": "mon"}
    assert t["requirements"]["min_age"] == 18 and {"key": "vehicle_rc_insurance", "step": "insurance"} in t["requirements"]["papers"]
    assert t["apps"] == {"android": None, "ios": None}
    assert "IN-TG-HYD" in [c["code"] for c in t["cities"]] and all(c["code"].startswith("IN-") for c in t["cities"])


async def test_boise_terms_are_in_dollars_and_miles(client: AsyncClient) -> None:
    t = (await client.get("/api/v1/delivery/terms", params={"city": "US-ID-BOI"})).json()
    assert t["currency"] == "USD" and t["distance_unit"] == "mi"
    assert Decimal(t["example"]["distance"]) == 2 and Decimal(t["example"]["total"]) == 5  # $3.00 + 2 mi x $1.00
    assert t["hourly_floor"] is None and t["batch_bonus"] is None
    assert [d["key"] for d in t["requirements"]["papers"]] == ["drivers_license", "vehicle_insurance", "payout_account",
                                                                  "background_check"] and "car" in t["requirements"]["vehicles"]


async def test_hidden_and_unknown_cities_are_404(client: AsyncClient) -> None:
    for code in ("IN-TG-WGL", "IN-AP-VSKP", "ZZ-ZZ-ZZZ"):  # draft, coming soon, no such city
        assert (await client.get("/api/v1/delivery/terms", params={"city": code})).status_code == 404
    assert (await client.get("/api/v1/delivery/terms", params={"city": "hyderabad"})).status_code == 422
    assert (await client.get("/api/v1/delivery/terms")).status_code == 422


async def test_admin_edits_requirements_and_store_links(client: AsyncClient) -> None:
    h = await _admin(client)
    before = (await client.get("/api/v1/delivery/terms", params={"city": "US-ID-BOI"})).json()["requirements"]
    dp = {"min_age": 19, "vehicles": ["car"], "documents": ["drivers_license", "vehicle_insurance", "payout_account",
                                                             "background_check"],
          "example_trip": {"distance": 2}, "app_links": {"android": "https://play.google.com/store/apps/details?id=x", "ios": None}}
    try:
        r = await client.patch("/api/v1/markets/countries/US", headers=h, json={"settings": {"delivery_partner": dp}})
        assert r.status_code == 200, r.text
        t = (await client.get("/api/v1/delivery/terms", params={"city": "US-ID-BOI"})).json()
        assert t["requirements"]["min_age"] == 19 and t["requirements"]["vehicles"] == ["car"]
        assert t["apps"]["android"].startswith("https://play.google.com/") and t["apps"]["ios"] is None
        bad = {**dp, "documents": ["passport"]}
        r = await client.patch("/api/v1/markets/countries/US", headers=h, json={"settings": {"delivery_partner": bad}})
        assert r.status_code in (400, 409, 422) and "Delivery partners" in r.text
    finally:
        restore = {**dp, "min_age": before["min_age"], "vehicles": before["vehicles"],
                   "documents": [d["key"] for d in before["papers"]],
                   "app_links": {"android": None, "ios": None}}
        assert (await client.patch("/api/v1/markets/countries/US", headers=h,
                                   json={"settings": {"delivery_partner": restore}})).status_code == 200
