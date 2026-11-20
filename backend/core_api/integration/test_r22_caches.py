"""R22: the version-keyed caches (shared/cache_versions.py) never show an edit late.

Each test fills a cache (and checks it was used), edits what it holds, through the API
or behind the API's back (SQL in another connection, as a script or psql would), and
expects the very next request to show the edit. Every edit is undone at the end.
"""
import os
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from core_api.modules.identity.tests.signin import login_response

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
SPICE_ROUTE = "spice-route-kitchen-madhapur"
JUBILEE_HILLS = (17.43, 78.41)


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


ADMIN_PW = "BhojanGoAdmin1"  # the seeded admins' (core_api/integration/test_rules.py)


async def auth(client: AsyncClient, email: str, pw: str = "BhojanGo123") -> dict:
    r = await login_response(client, email, pw)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def sql(statement: str, **params) -> None:  # type: ignore[no-untyped-def]
    """An edit the API never sees (its own connection and transaction)."""
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text(statement), params)
        await db.commit()


async def spice(client: AsyncClient) -> str:
    return next(r["id"] for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["slug"] == SPICE_ROUTE)


async def menu_items(client: AsyncClient, rid: str) -> dict:
    r = await client.get(f"/api/v1/restaurants/{rid}/menu")
    assert r.status_code == 200, r.text
    return {i["name"]: i for c in r.json()["categories"] for i in c["items"]}


async def test_menu_is_cached_and_every_kind_of_edit_shows_at_once(client: AsyncClient) -> None:
    from core_api.modules.catalog.api.v1.restaurants import _menus

    rid = await spice(client)
    first = await menu_items(client, rid)
    hits = _menus.hits
    assert await menu_items(client, rid) == first
    assert _menus.hits == hits + 1, "the second read is the cached answer"

    tikka = first["Paneer Tikka"]
    raita = next(o for g in first["Chicken Dum Biryani"]["option_groups"] for o in g["options"] if o["name"] == "Extra raita")
    try:
        # A price, behind the API's back.
        await sql("UPDATE menu_items SET price = price + 1 WHERE id = :i", i=tikka["id"])
        assert (await menu_items(client, rid))["Paneer Tikka"]["price"] == tikka["price"] + 1
        # An option's price (the trigger finds the kitchen through its group).
        await sql("UPDATE options SET price = price + 5 WHERE id = :i", i=raita["id"])
        got = next(o for g in (await menu_items(client, rid))["Chicken Dum Biryani"]["option_groups"]
                   for o in g["options"] if o["name"] == "Extra raita")
        assert Decimal(got["price"]) == Decimal(raita["price"]) + 5
        # Sold out today, through the partner app.
        partner = await auth(client, "partner.hyd@example.com")
        r = await client.put(f"/api/v1/restaurants/{rid}/menu-items/{tikka['id']}/sold-out", headers=partner,
                             json={"sold_out": True})
        assert r.status_code == 200, r.text
        assert (await menu_items(client, rid))["Paneer Tikka"]["sold_out_today"] is True
        await client.put(f"/api/v1/restaurants/{rid}/menu-items/{tikka['id']}/sold-out", headers=partner,
                         json={"sold_out": False})
        assert (await menu_items(client, rid))["Paneer Tikka"]["sold_out_today"] is False
        # The kitchen's own details (its name is on the menu).
        await sql("UPDATE restaurants SET description = description || ' (r22)' WHERE id = :i", i=rid)
        r = await client.get(f"/api/v1/restaurants/{rid}/menu")
        assert r.json()["restaurant"]["description"].endswith(" (r22)")
    finally:
        await sql("UPDATE menu_items SET price = :p WHERE id = :i", p=Decimal(str(tikka["price"])), i=tikka["id"])
        await sql("UPDATE options SET price = :p WHERE id = :i", p=Decimal(raita["price"]), i=raita["id"])
        await sql("UPDATE restaurants SET description = replace(description, ' (r22)', '') WHERE id = :i", i=rid)
    assert (await menu_items(client, rid))["Paneer Tikka"]["price"] == tikka["price"]


async def test_a_cached_menu_never_reaches_someone_who_may_not_see_it(client: AsyncClient) -> None:
    """R19/R20: a kitchen in a review-only city is 404 for everyone but its review accounts,
    cached or not; making the city review-only shows at once."""
    rid = await spice(client)
    assert (await client.get(f"/api/v1/restaurants/{rid}/menu")).status_code == 200  # cached now
    reviewer = str(uuid.uuid4())
    try:
        await sql("UPDATE cities SET settings = coalesce(settings, '{}'::jsonb) || jsonb_build_object("
                  "'review_only', true, 'review_accounts', jsonb_build_array(CAST(:u AS text))) WHERE code = 'IN-TG-HYD'",
                  u=reviewer)
        assert (await client.get(f"/api/v1/restaurants/{rid}/menu")).status_code == 404
        assert (await client.get(f"/api/v1/restaurants/{rid}/menu")).status_code == 404
    finally:
        await sql("UPDATE cities SET settings = settings - 'review_only' - 'review_accounts' WHERE code = 'IN-TG-HYD'")
    assert (await client.get(f"/api/v1/restaurants/{rid}/menu")).status_code == 200


async def test_an_approved_rule_prices_the_very_next_quote(client: AsyncClient) -> None:
    """Money: a kitchen's packaging levy, approved by a second admin, is on the next quote;
    paused, it is off the next one. The rules are cached until any rule changes."""
    from core_api.modules.rules.service.rules import _published

    rid = await spice(client)
    items = await menu_items(client, rid)
    customer = await auth(client, "customer1.hyd@example.com")
    cart = [{"menu_item_id": items["Paneer Tikka"]["id"], "quantity": 2}]

    async def packaging() -> str | None:
        r = await client.post("/api/v1/pricing/quote", headers=customer, json={
            "restaurant_id": rid, "items": cart, "deliver_to": {"lat": JUBILEE_HILLS[0], "lng": JUBILEE_HILLS[1]}})
        assert r.status_code == 200, r.text
        return next((ln["amount"] for ln in r.json()["lines"] if ln["code"] == "packaging"), None)

    before = await packaging()
    hits = _published.hits
    assert await packaging() == before
    assert _published.hits > hits, "the second quote used the cached rules"

    maker = await auth(client, "cm.in@example.com", ADMIN_PW)
    checker = await auth(client, "finance.in@example.com", ADMIN_PW)
    r = await client.post("/api/v1/rules", headers=maker, json={
        "family": "customer_fee", "template": "packaging_levy", "params": {"amount": 17},
        "scope_level": "restaurant", "scope_id": rid, "priority": 50})  # over the seeded kitchen levy (10)
    assert r.status_code == 201, r.text
    rule = r.json()["id"]
    try:
        await client.post(f"/api/v1/rules/{rule}/submit", headers=maker)
        assert await packaging() == before, "a rule waiting for approval prices nothing"
        r = await client.post(f"/api/v1/rules/{rule}/approve", headers=checker, json={})
        assert r.status_code == 200 and r.json()["status"] == "published", r.text
        assert await packaging() == "17.00"
        await sql("UPDATE rules SET paused_at = now(), paused_reason = 'r22 test' WHERE id = :i", i=rule)
        assert await packaging() == before
    finally:
        await sql("UPDATE rules SET paused_at = coalesce(paused_at, now()), paused_reason = 'r22 test' WHERE id = :i",
                  i=rule)


async def test_kitchen_pause_and_hours_stop_quotes_at_once(client: AsyncClient) -> None:
    """Availability (open, paused, hours) is read through the cached market and hours."""
    rid = await spice(client)
    items = await menu_items(client, rid)
    customer = await auth(client, "customer1.hyd@example.com")
    partner = await auth(client, "partner.hyd@example.com")
    cart = [{"menu_item_id": items["Paneer Tikka"]["id"], "quantity": 2}]

    async def quote() -> int:
        r = await client.post("/api/v1/pricing/quote", headers=customer, json={
            "restaurant_id": rid, "items": cart, "deliver_to": {"lat": JUBILEE_HILLS[0], "lng": JUBILEE_HILLS[1]}})
        return r.status_code

    assert await quote() == 200
    assert (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()["paused"] is False
    r = await client.put(f"/api/v1/restaurants/{rid}/pause", headers=partner, json={"paused": True, "minutes": 30})
    assert r.status_code == 200, r.text
    try:
        assert await quote() == 422
        assert (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()["paused"] is True
    finally:
        await client.put(f"/api/v1/restaurants/{rid}/pause", headers=partner, json={"paused": False})
    assert await quote() == 200
    # Closed for the day, behind the API's back (a day override for today and the days around it).
    await sql("UPDATE store_hour_overrides SET closed = true, opens = NULL, closes = NULL WHERE restaurant_id = :r", r=rid)
    try:
        assert await quote() == 422
    finally:
        from core_api.integration.conftest import open_all_day

        await open_all_day([rid])
    assert await quote() == 200


async def test_home_screen_shows_a_pause_at_once(client: AsyncClient) -> None:
    """GET /discover's per-address answer is keyed by the versions: a kitchen paused by an
    admin is shown closed by the next request, not after the minute the answer is kept."""
    rid = await spice(client)

    async def card() -> dict:
        r = await client.get("/api/v1/discover", params={"lat": JUBILEE_HILLS[0], "lng": JUBILEE_HILLS[1]})
        assert r.status_code == 200, r.text
        return next(c for c in r.json()["restaurants"] if c["id"] == rid)

    assert (await card())["closed_for_now"] is False
    await sql("UPDATE restaurants SET admin_paused_at = now() WHERE id = :i", i=rid)
    try:
        assert (await card())["closed_for_now"] is True
    finally:
        await sql("UPDATE restaurants SET admin_paused_at = NULL, admin_paused_until = NULL WHERE id = :i", i=rid)
    assert (await card())["closed_for_now"] is False


async def test_a_writing_session_never_fills_a_cache() -> None:
    """An uncommitted edit could be rolled back: what a session that wrote reads is never kept."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service import menu as menu_svc
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rid = (await db.execute(text("SELECT id FROM restaurants WHERE slug = :s"), {"s": SPICE_ROUTE})).scalar_one()
        r = await db.get(Restaurant, rid)
        await db.execute(text("UPDATE store_hour_overrides SET closed = true WHERE restaurant_id = :r"), {"r": rid})
        a = await menu_svc.availability(db, rid)
        assert a.open_now is False
        await db.rollback()
    async with AsyncSessionLocal() as db:
        assert (await menu_svc.availability(db, rid)).open_now is True
        assert r is not None


async def test_kitchen_board_shows_order_and_name_changes_at_once(client: AsyncClient) -> None:
    """The board is cached per kitchen until one of its orders changes (any writer), or a
    name on it, or a market. Who may see it is checked on every request."""
    from core_api.modules.orders.api.v1.orders import _boards
    from shared.db import AsyncSessionLocal

    rid = await spice(client)
    async with AsyncSessionLocal() as db:
        row = (await db.execute(text("SELECT id, special_instructions, customer_id FROM orders WHERE restaurant_id = :r "
                                     "ORDER BY created_at DESC LIMIT 1"), {"r": rid})).first()
    if row is None:
        pytest.skip("no Spice Route orders in this database yet")
    oid, note, customer = row
    partner = await auth(client, "partner.hyd@example.com")

    async def board() -> dict:
        r = await client.get(f"/api/v1/orders/restaurant/{rid}", headers=partner, params={"limit": 100})
        assert r.status_code == 200, r.text
        return next(o for o in r.json()["items"] if o["id"] == str(oid))

    await board()
    hits = _boards.hits
    await board()
    assert _boards.hits == hits + 1
    try:
        await sql("UPDATE orders SET special_instructions = 'r22: no onions' WHERE id = :i", i=oid)
        assert (await board())["special_instructions"] == "r22: no onions"
        await sql("UPDATE users SET full_name = 'Rtwotwo ' || full_name WHERE id = :u", u=customer)
        assert (await board())["customer"]["name"] == "Rtwotwo"
    finally:
        await sql("UPDATE orders SET special_instructions = :n WHERE id = :i", n=note, i=oid)
        await sql("UPDATE users SET full_name = substr(full_name, 10) WHERE id = :u AND full_name LIKE 'Rtwotwo %'",
                  u=customer)
    # Another kitchen's owner never gets this board, cached or not.
    other = await auth(client, "partner.boi@example.com")
    r = await client.get(f"/api/v1/orders/restaurant/{rid}", headers=other, params={"limit": 100})
    assert r.status_code == 403
