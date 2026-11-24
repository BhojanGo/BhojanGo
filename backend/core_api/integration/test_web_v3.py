"""Web v3 APIs on Postgres: order ratings and public stars, the active-order bar,
Notify-me counts, a city's prices, tip presets at checkout, cuisine photos.

    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration/test_web_v3.py -v
"""
import os
from datetime import timedelta

import pytest
from httpx import AsyncClient

from core_api.integration.test_account import sign_up, spice_and_biryani
from core_api.integration.test_orders_flow import client, login, new_order, pay, user_id  # noqa: F401
from core_api.integration.test_report_problem import chai_order, delivered

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def sql(statement: str, **params) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text(statement), params)
        await db.commit()


async def test_rate_a_delivered_order(client: AsyncClient) -> None:  # noqa: F811
    h = await sign_up(client, "Meera Iyer")
    order = await new_order(client, h)
    await pay(client, h, order)
    url = f"/api/v1/orders/{order['id']}/rating"
    r = await client.post(url, headers=h, json={"stars": 5})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_DELIVERED"
    await delivered(order["id"])
    assert (await client.get(url, headers=h)).json() is None  # not rated yet

    rest, _ = await spice_and_biryani(client)
    before = (await client.get(f"/api/v1/restaurants/by-slug/{rest['slug']}")).json()
    assert "rating_display" in before

    listed = (await client.get("/api/v1/orders", headers=h, params={"status": "delivered"})).json()["items"]
    assert listed[0]["id"] == order["id"] and listed[0]["rated"] is False and listed[0]["rating"] is None

    r = await client.post(url, headers=h, json={"stars": 4, "comment": "  Great biryani  "})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["stars"] == 4 and first["comment"] == "Great biryani" and first["editable"] is True
    assert first["order_id"] == order["id"] and first["restaurant_id"] == rest["id"]
    after = (await client.get(f"/api/v1/restaurants/by-slug/{rest['slug']}")).json()
    assert after["review_count"] == before["review_count"] + 1  # from the real ratings

    r = await client.post(url, headers=h, json={"stars": 5})  # edit within 7 days: still one rating
    assert r.status_code == 200 and r.json()["stars"] == 5 and r.json()["comment"] is None
    assert (await client.get(url, headers=h)).json()["stars"] == 5
    again = (await client.get(f"/api/v1/restaurants/by-slug/{rest['slug']}")).json()
    assert again["review_count"] == after["review_count"]

    listed = (await client.get("/api/v1/orders", headers=h, params={"status": "delivered"})).json()["items"]
    assert listed[0]["rated"] is True and listed[0]["rating"]["stars"] == 5

    # someone else's order; bad stars
    other = await login(client, "customer2.hyd@example.com")
    assert (await client.get(url, headers=other)).status_code == 404
    assert (await client.post(url, headers=other, json={"stars": 1})).status_code == 404
    for bad in ({"stars": 0}, {"stars": 6}, {"stars": 3, "comment": "x" * 501}):
        assert (await client.post(url, headers=h, json=bad)).status_code == 422

    # after 7 days it's final
    await sql("UPDATE reviews SET created_at = now() - interval '8 days' WHERE order_id = :o", o=order["id"])
    got = (await client.get(url, headers=h)).json()
    assert got["editable"] is False
    r = await client.post(url, headers=h, json={"stars": 1})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "RATING_LOCKED"


async def test_public_stars_wait_for_five_ratings(client: AsyncClient) -> None:  # noqa: F811
    rest, _ = await spice_and_biryani(client)
    was = (await client.get(f"/api/v1/restaurants/by-slug/{rest['slug']}")).json()
    await sql("UPDATE restaurants SET rating = 4.63, review_count = 23 WHERE id = :r", r=rest["id"])
    try:
        got = (await client.get(f"/api/v1/restaurants/by-slug/{rest['slug']}")).json()
        assert got["rating_display"] == {"new": False, "stars": 4.6, "count": 23}
        await sql("UPDATE restaurants SET review_count = 4 WHERE id = :r", r=rest["id"])
        assert (await client.get(f"/api/v1/restaurants/by-slug/{rest['slug']}")).json()["rating_display"]["new"] is True
    finally:
        await sql("UPDATE restaurants SET rating = :x, review_count = :n WHERE id = :r",
                  x=was["rating"], n=was["review_count"], r=rest["id"])
    d = (await client.get("/api/v1/discover", params={"city": "IN-TG-HYD"})).json()
    assert all("new" in k["rating_display"] for k in d["restaurants"])


async def test_active_order_bar(client: AsyncClient) -> None:  # noqa: F811
    h = await sign_up(client, "Kiran Das")
    order, _ = await chai_order(client, h, 6)
    await pay(client, h, order)
    active = (await client.get("/api/v1/orders", headers=h, params={"status": "active"})).json()["items"]
    mine = next(o for o in active if o["id"] == order["id"])
    assert mine["pin"] is None and mine["rider_first_name"] is None  # no rider yet: no PIN
    assert mine["eta"]  # the estimated delivery time

    rider = await login(client, "rider1.hyd@example.com")
    await sql("UPDATE orders SET driver_id = :d, status = 'picked_up', picked_up_at = now() WHERE id = :o",
              d=user_id(rider), o=order["id"])
    mine = next(o for o in (await client.get("/api/v1/orders", headers=h)).json()["items"] if o["id"] == order["id"])
    assert mine["rider_first_name"] and " " not in mine["rider_first_name"]
    assert mine["pin"] and len(mine["pin"]) == 4 and mine["pin"] == (await client.get(
        f"/api/v1/orders/{order['id']}", headers=h)).json()["pin"]

    await delivered(order["id"])
    done = next(o for o in (await client.get("/api/v1/orders", headers=h)).json()["items"] if o["id"] == order["id"])
    assert done["pin"] is None and done["rider_first_name"] is None and done["eta"] is None


async def test_waiting_counts(client: AsyncClient) -> None:  # noqa: F811
    me = f"wait-{os.urandom(4).hex()}@example.com"
    d0 = (await client.get("/api/v1/markets/directory")).json()
    cities = {c["code"]: c for k in d0["countries"] for r in k["regions"] for c in r["cities"]}
    n0 = cities["US-ID-NMP"]["waiting"]
    assert (await client.post("/api/v1/markets/waitlist", json={
        "email": me, "city_code": "US-ID-NMP", "consent": True, "source": "soon_city"})).status_code == 202
    d1 = (await client.get("/api/v1/markets/directory")).json()
    cities = {c["code"]: c for k in d1["countries"] for r in k["regions"] for c in r["cities"]}
    assert cities["US-ID-NMP"]["waiting"] == n0 + 1
    assert cities["IN-TG-HYD"]["waiting"] == 0  # live
    assert (await client.get("/api/v1/markets/cities/us/nampa")).json()["waiting"] == n0 + 1
    assert (await client.get("/api/v1/markets/cities/in/hyderabad")).json()["waiting"] == 0


async def test_city_pricing_from_the_rules(client: AsyncClient) -> None:  # noqa: F811
    p = (await client.get("/api/v1/markets/cities/in/hyderabad")).json()["pricing"]
    assert p["currency"] == "INR" and p["distance_unit"] == "km"
    fee = p["delivery_fee"]
    assert fee["type"] == "distance_slabs"  # R31: distance bands
    assert [(float(s["up_to"]), float(s["fee"])) for s in fee["slabs"]] == [(3, 30), (5, 40), (7, 50)]
    assert float(p["delivery_from"]) == 30
    assert p["service_fee"] is None  # R29: the platform fee replaced it
    assert {k: float(v) for k, v in p["platform_fee"].items()} == {"percent": 10, "min": 15}
    assert {k: float(v) for k, v in p["small_order_fee"].items()} == {"below": 99, "fee": 15}
    assert [float(a) for a in p["tip_presets"]["amounts"]] == [10, 20, 30] and p["tip_presets"]["default_index"] == 1
    assert float(p["max_distance"]) == 7  # R31: the last band
    assert all(m["zone"] and float(m["min_order"]) >= 0 for m in p["min_order"])
    us = (await client.get("/api/v1/markets/cities/us/boise")).json()["pricing"]
    assert us["currency"] == "USD" and us["distance_unit"] == "mi" and float(us["delivery_from"]) == 3.5  # R31: 0-2 mi $3.50
    # a coming-soon city is priced by its country's rules
    soon = (await client.get("/api/v1/markets/cities/us/nampa")).json()["pricing"]
    assert soon["delivery_fee"]["type"] == "distance_slabs" and float(soon["tip_presets"]["amounts"][0]) == 2


async def test_quote_has_tip_presets(client: AsyncClient) -> None:  # noqa: F811
    h = await login(client, "customer1.hyd@example.com")
    rest, biryani = await spice_and_biryani(client)
    q = await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rest["id"], "items": [{"menu_item_id": biryani["id"], "quantity": 1}],
        "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    assert q.status_code == 200, q.text
    tips = q.json()["tip_presets"]
    assert [float(a) for a in tips["amounts"]] == [10, 20, 30] and tips["default_index"] == 1


async def test_us_bag_under_the_restaurant_minimum_is_priced_but_not_placed(client: AsyncClient) -> None:  # noqa: F811
    """R36 (was round 6's zone minimum): no zone has a minimum any more. A Boise bag under Boise Bowl Co.'s
    own $15 minimum still gets the whole bill with the US tip buttons, plus how much is missing; placing it
    is refused (BELOW_MINIMUM, "Add $2.00 more ..."). Two bowls clear it."""
    import uuid

    h = await login(client, "customer1.boi@example.com")
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Boise Bowl Co.")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    tofu = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Crispy Tofu Bowl")  # $13.00
    downtown = {"lat": 43.6150, "lng": -116.2023}

    def bag(n: int) -> dict:
        return {"restaurant_id": rest["id"], "items": [{"menu_item_id": tofu["id"], "quantity": n}], "deliver_to": downtown}

    r = await client.post("/api/v1/pricing/quote", headers=h, json=bag(1))
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["restaurant_minimum"] == "15.00" and q["short_by"] == "2.00"
    assert any(ln["code"] == "food" for ln in q["lines"]) and float(q["total"]) > 13
    assert [float(a) for a in q["tip_presets"]["amounts"]] == [2, 3, 5] and q["tip_presets"]["default_index"] == 1
    placed = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": bag(1)["items"], "payment_method": "card", "quote_token": q["token"],
        "delivery_address": {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}})
    assert placed.status_code == 409, placed.text
    d = placed.json()["detail"]
    assert d["code"] == "BELOW_MINIMUM" and d["message"] == "Add $2.00 more to order from Boise Bowl Co."

    q2 = await client.post("/api/v1/pricing/quote", headers=h, json=bag(2))
    assert q2.status_code == 200, q2.text
    assert q2.json()["short_by"] == "0.00" and q2.json()["restaurant_minimum"] == "15.00"


async def test_cuisines_have_two_kitchens_and_their_own_photos(client: AsyncClient) -> None:  # noqa: F811
    from shared.redis import get_redis

    await (await get_redis()).delete("discover:IN-TG-HYD")
    d = (await client.get("/api/v1/discover", params={"city": "IN-TG-HYD"})).json()
    assert d["cuisines"] and all(c["count"] >= 2 for c in d["cuisines"])
    photos = [c["photo"] for c in d["cuisines"] if "photo" in c]
    assert len(photos) == len(set(photos))  # never the same photo twice
    names = {c["name"] for c in d["cuisines"]}
    assert "South Indian" in names  # Curry Leaf and Banjara Dosa Co.
    assert next(c for c in d["cuisines"] if c["name"] == "South Indian").get("photo")


def test_edit_window_is_seven_days() -> None:
    from core_api.modules.catalog.service.ratings import EDIT_WINDOW

    assert EDIT_WINDOW == timedelta(days=7)


async def test_search_finds_dishes_and_old_city_is_pickup_only(client: AsyncClient) -> None:  # noqa: F811
    """R36: /discover/search finds dishes by name in every kitchen that has one (against their own menus);
    from Old City, Spice Route Kitchen (Madhapur, takes pickup) is too far to deliver: pickup only, listed after
    the kitchens that deliver and before the ones that are too far without pickup."""
    old_city = {"lat": 17.3620, "lng": 78.4750}
    d = (await client.get("/api/v1/discover", params=old_city)).json()
    spice = next(k for k in d["restaurants"] if k["slug"] == "spice-route-kitchen-madhapur")
    assert spice["deliverable"] is False and spice["pickup_enabled"] is True and spice["pickup_only"] is True
    assert spice["pickup_fee_percent"] == "5" and spice["delivery_fee"] is None

    def group(k: dict) -> int:
        if k["open_now"] and k["deliverable"]:
            return 0
        if k["open_now"] and k["pickup_only"]:
            return 1
        return 2 if (k["deliverable"] or k["pickup_only"]) else 3
    assert [group(k) for k in d["restaurants"]] == sorted(group(k) for k in d["restaurants"])

    madhapur = {"lat": 17.4483, "lng": 78.3915}
    near = (await client.get("/api/v1/discover", params=madhapur)).json()["restaurants"]
    want = set()
    for k in near:
        m = (await client.get(f"/api/v1/restaurants/{k['id']}/menu")).json()
        for i in [i for c in m["categories"] for i in c["items"]] + m.get("uncategorized_items", []):
            if "biryani" in i["name"].lower() and i.get("is_available", True):
                want.add((k["id"], i["id"]))
    s = (await client.get("/api/v1/discover/search", params={"q": "Biryani", **madhapur})).json()
    assert want and {(x["restaurant_id"], x["id"]) for x in s["dishes"]} == want
    assert all("biryani" in x["name"].lower() and float(x["price"]) > 0 for x in s["dishes"])
    assert (await client.get("/api/v1/discover/search", params={"q": "b", **madhapur})).status_code == 422  # 2+ characters
