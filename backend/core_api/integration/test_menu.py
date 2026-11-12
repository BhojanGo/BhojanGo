"""P10 on a migrated, seeded database: option groups, sold out today, store
hours and holidays, prep time, and FSSAI licences pausing listings."""
import os
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.conftest import open_all_day

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def login(client: AsyncClient, email: str, pw: str = "BhojanGo123") -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def restaurant(client: AsyncClient, name: str) -> tuple[dict, dict]:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if r["name"] == name)
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    items = {i["name"]: i for c in menu["categories"] for i in c["items"]}
    return rest, items


async def quote(client: AsyncClient, h: dict, rid: str, items: list[dict], where=(17.4483, 78.3915)):
    return await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": items, "deliver_to": {"lat": where[0], "lng": where[1]}})


async def test_menu_has_real_option_groups(client: AsyncClient) -> None:
    _, items = await restaurant(client, "Spice Route Kitchen")
    biryani = items["Chicken Dum Biryani"]
    groups = {g["name"]: g for g in biryani["option_groups"]}
    assert (groups["Size"]["min_picks"], groups["Size"]["max_picks"]) == (1, 1)
    assert (groups["Add-ons"]["min_picks"], groups["Add-ons"]["max_picks"]) == (0, 3)
    assert {o["name"]: o["price"] for o in groups["Add-ons"]["options"]} == {"Extra raita": "40.00", "Mirchi ka salan": "30.00"}
    # The pre-P10 shape is still there for current apps, now with ids.
    legacy = {c["name"]: c for c in biryani["customizations"]}
    assert legacy["Size"]["required"] is True and legacy["Size"]["id"] == groups["Size"]["id"]
    assert biryani["sold_out_today"] is False


async def test_quote_by_option_ids_and_pick_limits(client: AsyncClient) -> None:
    h = await login(client, "customer1.hyd@example.com")
    rest, items = await restaurant(client, "Spice Route Kitchen")
    b = items["Chicken Dum Biryani"]
    g = {x["name"]: x for x in b["option_groups"]}
    pick = lambda group, name: {"group": g[group]["id"], "option": next(o["id"] for o in g[group]["options"] if o["name"] == name)}  # noqa: E731

    ok = [pick("Size", "Family · serves 3"), pick("Spice", "Hot"), pick("Add-ons", "Extra raita"), pick("Add-ons", "Mirchi ka salan")]
    r = await quote(client, h, rest["id"], [{"menu_item_id": b["id"], "quantity": 1, "options": ok}])
    assert r.status_code == 200, r.text
    food = next(ln for ln in r.json()["lines"] if ln["code"] == "food")
    assert food["amount"] == "850.00"  # 300 + family 480 + raita 40 + salan 30

    cases = [
        ([pick("Spice", "Hot")], "choose size"),
        ([pick("Size", "Family · serves 3"), pick("Size", "Regular · serves 1"), pick("Spice", "Hot")], "at most 1"),
        ([pick("Size", "Family · serves 3"), pick("Spice", "Hot"), pick("Add-ons", "Extra raita"), pick("Add-ons", "Extra raita")], "each option once"),
    ]
    for options, words in cases:
        r = await quote(client, h, rest["id"], [{"menu_item_id": b["id"], "quantity": 1, "options": options}])
        assert r.status_code == 422 and words in r.text.lower(), (words, r.text)


async def test_partner_builds_a_group_and_marks_an_option_unavailable(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    customer = await login(client, "customer1.hyd@example.com")
    rest, items = await restaurant(client, "Spice Route Kitchen")
    tikka = items["Paneer Tikka"]
    r = await client.post(f"/api/v1/restaurants/{rest['id']}/option-groups", headers=partner, json={
        "name": "Dips", "min_picks": 0, "max_picks": 1,
        "options": [{"name": "Mint chutney", "price": 0}, {"name": "Garlic mayo", "price": 25}]})
    assert r.status_code == 201, r.text
    group = r.json()
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/menu-items/{tikka['id']}/option-groups", headers=partner,
                         json={"group_ids": [group["id"]]})
    assert r.status_code == 200 and r.json()["option_groups"][0]["name"] == "Dips"

    mayo = {"group": "Dips", "option": "Garlic mayo"}
    r = await quote(client, customer, rest["id"], [{"menu_item_id": tikka["id"], "quantity": 1, "options": [mayo]}])
    assert r.status_code == 200 and next(ln for ln in r.json()["lines"] if ln["code"] == "food")["amount"] == "245.00"

    opts = [{"id": o["id"], "name": o["name"], "price": o["price"], "is_available": o["name"] != "Garlic mayo"} for o in group["options"]]
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/option-groups/{group['id']}", headers=partner,
                         json={"name": "Dips", "min_picks": 0, "max_picks": 1, "options": opts})
    assert r.status_code == 200, r.text
    r = await quote(client, customer, rest["id"], [{"menu_item_id": tikka["id"], "quantity": 1, "options": [mayo]}])
    assert r.status_code == 422 and "unavailable today" in r.text

    bad = await client.post(f"/api/v1/restaurants/{rest['id']}/option-groups", headers=partner, json={
        "name": "Broken", "min_picks": 3, "max_picks": 2, "options": [{"name": "x"}]})
    assert bad.status_code == 422
    # Clean up so other tests see the seeded menu.
    await client.put(f"/api/v1/restaurants/{rest['id']}/menu-items/{tikka['id']}/option-groups", headers=partner, json={"group_ids": []})
    await client.delete(f"/api/v1/restaurants/{rest['id']}/option-groups/{group['id']}", headers=partner)


@pytest.mark.parametrize(("email", "pw", "status"), [
    ("partner.hyd@example.com", "BhojanGo123", 200),      # the owner
    ("ops.hyd@example.com", "BhojanGoAdmin1", 200),        # city ops in Hyderabad (partners.edit)
    ("partner.boi@example.com", "BhojanGo123", 403),       # another partner
    ("ops.boi@example.com", "BhojanGoAdmin1", 403),        # city ops elsewhere
    ("viewer@example.com", "BhojanGoAdmin1", 403),
])
async def test_who_can_mark_sold_out(client: AsyncClient, email, pw, status) -> None:
    rest, items = await restaurant(client, "Spice Route Kitchen")
    h = await login(client, email, pw)
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/menu-items/{items['Double Ka Meetha']['id']}/sold-out",
                         headers=h, json={"sold_out": False})
    assert r.status_code == status, r.text


async def test_sold_out_today(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    customer = await login(client, "customer1.hyd@example.com")
    rest, items = await restaurant(client, "Spice Route Kitchen")
    tikka = items["Paneer Tikka"]
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/menu-items/{tikka['id']}/sold-out", headers=partner, json={"sold_out": True})
    assert r.status_code == 200 and r.json()["sold_out_today"] is True
    until = datetime.fromisoformat(r.json()["sold_out_until"])
    assert until.utcoffset() == timedelta(hours=5, minutes=30) and (until.hour, until.minute) == (0, 0)  # IST midnight
    try:
        _, items = await restaurant(client, "Spice Route Kitchen")
        assert items["Paneer Tikka"]["sold_out_today"] is True
        r = await quote(client, customer, rest["id"], [{"menu_item_id": tikka["id"], "quantity": 1}])
        assert r.status_code == 422 and "sold out today" in r.text
    finally:
        await client.put(f"/api/v1/restaurants/{rest['id']}/menu-items/{tikka['id']}/sold-out", headers=partner, json={"sold_out": False})
    r = await quote(client, customer, rest["id"], [{"menu_item_id": tikka["id"], "quantity": 1}])
    assert r.status_code == 200


async def test_holiday_closes_the_restaurant(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    customer = await login(client, "customer4.hyd@example.com")
    rest, items = await restaurant(client, "Curry Leaf")
    today = datetime.now(UTC).astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata")).date()
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/hours/overrides/{today}", headers=partner,
                         json={"closed": True, "note": "Staff holiday"})
    assert r.status_code == 200, r.text
    try:
        a = (await client.get(f"/api/v1/restaurants/{rest['id']}/availability")).json()
        assert a["open_now"] is False and "Staff holiday" in a["reason"] and a["timezone"] == "Asia/Kolkata"
        r = await quote(client, customer, rest["id"], [{"menu_item_id": next(iter(items.values()))["id"], "quantity": 2}],
                        where=(17.4401, 78.3489))
        assert r.status_code == 422 and "Staff holiday" in r.text
    finally:
        await open_all_day([rest["id"]])
    assert (await client.get(f"/api/v1/restaurants/{rest['id']}/availability")).json()["open_now"] is True


async def test_weekly_hours_and_prep_time(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    rest, _ = await restaurant(client, "Banjara Dosa Co.")
    weekly = [{"weekday": d, "opens": "07:00", "closes": "11:00"} for d in range(7)] + \
             [{"weekday": d, "opens": "17:00", "closes": "01:00"} for d in (4, 5)]
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/hours", headers=partner, json={"weekly": weekly})
    assert r.status_code == 200 and len(r.json()["weekly"]) == 9
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/hours", headers=partner,
                         json={"weekly": [{"weekday": 0, "opens": "09:00", "closes": "09:00"}]})
    assert r.status_code == 422
    r = await client.put(f"/api/v1/restaurants/{rest['id']}/prep-time", headers=partner, json={"minutes": 25})
    assert r.json()["avg_prep_minutes"] == 25
    assert (await client.put(f"/api/v1/restaurants/{rest['id']}/prep-time", headers=partner, json={"minutes": 1})).status_code == 422


async def test_expired_fssai_pauses_the_listing(client: AsyncClient) -> None:
    admin = await login(client, "cm.in@example.com", "BhojanGoAdmin1")
    customer = await login(client, "customer5.hyd@example.com")
    rest, items = await restaurant(client, "Charminar Chai House")
    rid = rest["id"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = await client.put(f"/api/v1/restaurants/{rid}/licence", headers=admin,
                         json={"fssai_number": rest["fssai_number"], "fssai_expires_on": yesterday})
    assert r.status_code == 200, r.text
    try:
        a = (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()
        assert a["listed"] is False and a["paused_reason"] == "fssai_expired"
        r = await quote(client, customer, rid, [{"menu_item_id": next(iter(items.values()))["id"], "quantity": 2}],
                        where=(17.3616, 78.4747))
        assert r.status_code == 422 and "Temporarily unavailable" in r.text

        r = await client.post("/api/v1/restaurants/licences/check", headers=admin)
        assert rid in r.json()["paused"]
        names = [x["name"] for x in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]]
        assert "Charminar Chai House" not in names
        assert (await client.post("/api/v1/restaurants/licences/check", headers=admin)).json()["paused"] == []  # idempotent
        bad = await client.put(f"/api/v1/restaurants/{rid}/licence", headers=admin,
                               json={"fssai_number": "123", "fssai_expires_on": "2030-01-01"})
        assert bad.status_code == 422
    finally:
        r = await client.put(f"/api/v1/restaurants/{rid}/licence", headers=admin,
                             json={"fssai_number": rest["fssai_number"], "fssai_expires_on": "2027-03-31"})
    assert r.json()["paused_reason"] is None
    names = [x["name"] for x in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]]
    assert "Charminar Chai House" in names
