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
    assert fee["type"] == "distance_slabs"
    assert [(float(s["up_to"]), float(s["fee"])) for s in fee["slabs"]] == [(3, 25), (6, 35), (10, 50)]
    assert float(p["delivery_from"]) == 25
    assert {k: float(v) for k, v in p["service_fee"].items()} == {"percent": 2, "min": 5, "max": 15}
    assert {k: float(v) for k, v in p["small_order_fee"].items()} == {"below": 99, "fee": 15}
    assert [float(a) for a in p["tip_presets"]["amounts"]] == [10, 20, 30] and p["tip_presets"]["default_index"] == 1
    assert float(p["max_distance"]) == 10
    assert all(m["zone"] and float(m["min_order"]) >= 0 for m in p["min_order"])
    us = (await client.get("/api/v1/markets/cities/us/boise")).json()["pricing"]
    assert us["currency"] == "USD" and us["distance_unit"] == "mi" and float(us["delivery_from"]) == 1.99
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


async def test_us_bag_under_the_minimum_reads_dollars_and_keeps_us_tips(client: AsyncClient) -> None:  # noqa: F811
    """Round 6: a Boise bag under Downtown's $15 minimum is refused as MIN_ORDER with
    the amount for the client to format ("$15", never "USD 15") and the US
    tip_presets rule's buttons; a bag over it is quoted with the same buttons."""
    h = await login(client, "customer1.boi@example.com")
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Boise Bowl Co.")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    tofu = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Crispy Tofu Bowl")  # $13.00
    downtown = {"lat": 43.6150, "lng": -116.2023}

    def bag(n: int) -> dict:
        return {"restaurant_id": rest["id"], "items": [{"menu_item_id": tofu["id"], "quantity": n}], "deliver_to": downtown}

    r = await client.post("/api/v1/pricing/quote", headers=h, json=bag(1))
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["code"] == "MIN_ORDER" and d["zone"] == "Downtown"
    assert (d["amount"], d["currency"]) == ("15.00", "USD")
    assert d["message"] == "The minimum order in Downtown is $15"
    assert [float(a) for a in d["tip_presets"]["amounts"]] == [2, 3, 5] and d["tip_presets"]["default_index"] == 1

    q = await client.post("/api/v1/pricing/quote", headers=h, json=bag(2))
    assert q.status_code == 200, q.text
    assert [float(a) for a in q.json()["tip_presets"]["amounts"]] == [2, 3, 5]


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
