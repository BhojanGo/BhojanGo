"""R19: the store review accounts (tools/review_accounts.py) and their hidden city.

The command makes a review-only city in the open sea with a customer, an approved
kitchen and an approved delivery partner. Nobody else finds the city or its kitchen
(locate, discover, the public lists, the kitchen's page and menu); the review
customer does, and can price a cart there. Running it again refuses.
"""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.modules.identity.tests.signin import login_response

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


def command():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "tools" / "review_accounts.py"
    spec = importlib.util.spec_from_file_location("review_accounts", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def bearer(client: AsyncClient, email: str, pw: str) -> dict:
    r = await login_response(client, email, pw)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def remove(code: str, emails: list[str]) -> None:
    """Leave the shared database as the seed made it (other tests list US cities)."""
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        ids = [r for (r,) in (await db.execute(text("SELECT id FROM users WHERE email = ANY(:e)"), {"e": emails})).all()]
        await db.execute(text("DELETE FROM restaurants WHERE owner_id = ANY(:u)"), {"u": ids})
        await db.execute(text("DELETE FROM zones WHERE city_id IN (SELECT id FROM cities WHERE code = :c)"), {"c": code})
        await db.execute(text("DELETE FROM cities WHERE code = :c"), {"c": code})
        await db.execute(text("DELETE FROM legal_acceptances WHERE user_id = ANY(:u)"), {"u": ids})
        await db.execute(text("DELETE FROM users WHERE id = ANY(:u)"), {"u": ids})
        await db.commit()


async def test_review_accounts_see_their_hidden_city_and_nobody_else_does(client: AsyncClient) -> None:
    from shared.db import AsyncSessionLocal

    cmd = command()
    args = cmd.parse_args(["--email-domain", f"r{uuid.uuid4().hex[:8]}.example.com"])
    emails = list(cmd.emails(args.email_domain).values())
    code = "US-ID-REV"
    try:
        async with AsyncSessionLocal() as db:
            logins = {row.who: row for row in await cmd.create(db, args)}
            await db.commit()
        # Idempotent by refusing: a second run changes nothing.
        async with AsyncSessionLocal() as db:
            with pytest.raises(cmd.Refused):
                await cmd.create(db, args)
            await db.rollback()

        review = await bearer(client, logins["BhojanGo"].email, logins["BhojanGo"].password)
        other = await bearer(client, "customer1.boi@example.com", "BhojanGo123")
        lat, lng = cmd.CENTRES["US"]
        home = {"lat": lat + 0.01, "lng": lng}

        # Locate and discover: served for the review customer only.
        for h, served in (({}, False), (other, False), (review, True)):
            loc = (await client.get("/api/v1/markets/locate", params=home, headers=h)).json()
            assert loc["serviceable"] is served and (loc.get("city_code") == code) is served, loc
            d = await client.get("/api/v1/discover", params=home, headers=h)
            assert d.status_code == 200 and d.json()["served"] is served, d.text
            names = [k["name"] for k in d.json().get("restaurants") or []]
            assert (cmd.KITCHEN_NAME in names) is served, names
            assert (await client.get("/api/v1/discover", params={"city": code}, headers=h)).status_code == (200 if served else 404)
        # Asked again by someone else right after (the cache): still nothing.
        assert (await client.get("/api/v1/discover", params=home)).json()["served"] is False

        # The kitchen: its page and menu only for the review accounts; never in public lists.
        kitchen = next(k for k in (await client.get("/api/v1/discover", params=home, headers=review)).json()["restaurants"]
                       if k["name"] == cmd.KITCHEN_NAME)
        for h, status in (({}, 404), (other, 404), (review, 200)):
            assert (await client.get(f"/api/v1/restaurants/{kitchen['id']}/menu", headers=h)).status_code == status
            assert (await client.get(f"/api/v1/restaurants/{kitchen['id']}", headers=h)).status_code == status
        assert (await client.get(f"/api/v1/restaurants/by-slug/{kitchen['slug']}")).status_code == 404
        listed = (await client.get("/api/v1/restaurants", params={"country": "US", "limit": 100})).json()["items"]
        assert cmd.KITCHEN_NAME not in [k["name"] for k in listed]
        assert code not in [c["code"] for c in (await client.get("/api/v1/markets/cities")).json()]
        directory = (await client.get("/api/v1/markets/directory")).json()
        assert code not in [c["code"] for k in directory["countries"] for r in k["regions"] for c in r["cities"]]
        areas = (await client.get("/api/v1/markets/areas", params={"q": "App Review"})).json()
        assert areas == []
        assert (await client.get("/api/v1/markets/cities/us/app-review")).status_code == 404

        # The review customer can price a cart there (pricing isn't hidden).
        menu = (await client.get(f"/api/v1/restaurants/{kitchen['id']}/menu", headers=review)).json()
        item = menu["categories"][0]["items"][0]
        q = await client.post("/api/v1/pricing/quote", headers=review, json={
            "restaurant_id": kitchen["id"], "items": [{"menu_item_id": item["id"], "quantity": 1}], "deliver_to": home})
        assert q.status_code == 200, q.text

        # The delivery partner is approved; the kitchen owner has the kitchen.
        rider = await bearer(client, logins["BhojanGo Delivery"].email, logins["BhojanGo Delivery"].password)
        assert (await client.get("/api/v1/riders/me/onboarding", headers=rider)).json()["ready"] is True
        await bearer(client, logins["BhojanGo Kitchen"].email, logins["BhojanGo Kitchen"].password)
    finally:
        await remove(code, emails)
