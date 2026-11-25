"""R43: menu editing on a migrated, seeded database.

Edit a dish (every field), add and soft-delete one (old orders keep its name and price), categories (add, rename,
reorder, hide, schedule), options with prices and min/max, price rules (> 0, 2 decimals, whole rupees, the >50%
confirmation), the history (who, when, old -> new; the restaurant and admins), dish search, and the held price:
a quote keeps its price when the restaurant raises it; once it expires, the new quote has the new price.

Each test adds its own dishes and categories (names with a random tag) and puts back what it changed, so the rest
of the suite sees the seed menu.
"""
import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.modules.identity.tests.signin import login_response

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
HYD = (17.4483, 78.3915)
ADDRESS = {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}


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
    r = await login_response(client, email, pw)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def spice_route(client: AsyncClient) -> dict:
    return next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")


async def public_items(client: AsyncClient, rid: str) -> dict[str, dict]:
    menu = (await client.get(f"/api/v1/restaurants/{rid}/menu")).json()
    return {i["name"]: i for c in menu["categories"] for i in c["items"]} | {i["name"]: i for i in menu["uncategorized_items"]}


async def add_dish(client: AsyncClient, h: dict, rid: str, name: str, price: str, **more) -> dict:  # type: ignore[no-untyped-def]
    r = await client.post(f"/api/v1/restaurants/{rid}/menu-items", headers=h,
                          json={"name": name, "price": price, "category": "Specials", **more})
    assert r.status_code == 201, r.text
    return r.json()


async def quote(client: AsyncClient, h: dict, rid: str, items: list[dict]):  # type: ignore[no-untyped-def]
    return await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": items, "deliver_to": {"lat": HYD[0], "lng": HYD[1]}})


def food(q: dict) -> str:
    return next(ln["amount"] for ln in q["lines"] if ln["code"] == "food")


async def history(client: AsyncClient, h: dict, rid: str, item_id: str) -> list[dict]:
    r = await client.get(f"/api/v1/restaurants/{rid}/menu/history", headers=h, params={"item_id": item_id})
    assert r.status_code == 200, r.text
    return r.json()["changes"]


async def test_edit_every_field_and_the_history(client: AsyncClient) -> None:
    partner, admin = await login(client, "partner.hyd@example.com"), await login(client, "admin@example.com", "BhojanGoAdmin1")
    rid = (await spice_route(client))["id"]
    tag = uuid.uuid4().hex[:6]
    cat = (await client.post(f"/api/v1/restaurants/{rid}/categories", headers=partner, json={"name": f"Tiffins {tag}"})).json()
    dish = await add_dish(client, partner, rid, f"Plain Dosa {tag}", "80", is_veg=True)
    r = await client.put(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner, json={
        "name": f"Masala Dosa {tag}", "description": "Potato masala, chutneys", "price": "110", "category_id": cat["id"],
        "is_veg": False, "spice_level": 2, "is_available": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["name"], out["price"], out["category"], out["category_id"], out["is_veg"], out["spice_level"]) == (
        f"Masala Dosa {tag}", 110.0, f"Tiffins {tag}", cat["id"], False, 2)
    # customers see it in its category
    assert (await public_items(client, rid))[f"Masala Dosa {tag}"]["price"] == 110.0

    rows = await history(client, partner, rid, dish["id"])
    changed = {c["field"]: (c["old"], c["new"]) for c in rows[0]["changes"]}
    assert rows[0]["action"] == "changed" and rows[0]["who"] == "you" and rows[0]["actor_kind"] == "restaurant"
    assert changed["price"] == ("80.00", "110.00") and changed["name"] == (f"Plain Dosa {tag}", f"Masala Dosa {tag}")
    assert changed["spice_level"] == (None, 2) and changed["is_veg"] == (True, False) and changed["category"] == ("Specials", f"Tiffins {tag}")
    assert rows[-1]["action"] == "added"

    # an admin's change: the admin sees their email, the restaurant sees "bhojango"
    r = await client.put(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=admin, json={"description": "Crisp"})
    assert r.status_code == 200, r.text
    assert (await history(client, admin, rid, dish["id"]))[0]["who"] == "admin@example.com"
    mine = (await history(client, partner, rid, dish["id"]))[0]
    assert mine["who"] == "bhojango" and mine["actor_kind"] == "admin"
    # clearing the spice level (null) is a change too
    r = await client.put(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner, json={"spice_level": None})
    assert r.json()["spice_level"] is None

    # wrong role: another restaurant's partner and a customer can't edit or read the history
    for who in (await login(client, "partner.boi@example.com"), await login(client, "customer1.hyd@example.com")):
        assert (await client.put(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=who, json={"price": "1"})).status_code == 403
        assert (await client.get(f"/api/v1/restaurants/{rid}/menu/history", headers=who)).status_code == 403
        assert (await client.get(f"/api/v1/restaurants/{rid}/menu/manage", headers=who)).status_code == 403
    await client.delete(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner)
    await client.put(f"/api/v1/restaurants/{rid}/categories/{cat['id']}", headers=partner, json={"is_active": False})


async def test_price_rules_and_the_big_change_confirmation(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    rid = (await spice_route(client))["id"]
    dish = await add_dish(client, partner, rid, f"Idli {uuid.uuid4().hex[:6]}", "60")
    url = f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}"
    r = await client.put(url, headers=partner, json={"price": "60.50"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PRICE_RULE" and "whole" in r.json()["detail"]["message"]
    assert (await client.put(url, headers=partner, json={"price": "0"})).status_code == 422
    assert (await client.put(url, headers=partner, json={"price": "-5"})).status_code == 422
    r = await client.post(f"/api/v1/restaurants/{rid}/menu-items", headers=partner, json={"name": "Vada half", "price": "45.5", "category": "x"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PRICE_RULE"
    # +50% exactly is fine; more needs a confirmation (409 with old, new and percent)
    assert (await client.put(url, headers=partner, json={"price": "90"})).status_code == 200
    r = await client.put(url, headers=partner, json={"price": "200"})
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert {k: d[k] for k in ("code", "old", "new", "percent")} == {"code": "PRICE_CONFIRM", "old": "90.00", "new": "200.00", "percent": 122}
    assert (await public_items(client, rid))[dish["name"]]["price"] == 90.0  # not saved
    r = await client.put(url, headers=partner, json={"price": "200", "confirm_price_change": True})
    assert r.status_code == 200 and r.json()["price"] == 200.0
    # a US restaurant: cents, at most 2 decimals
    boi = await login(client, "partner.boi@example.com")
    us = (await client.get("/api/v1/restaurants/mine", headers=boi)).json()[0]["id"]
    r = await client.post(f"/api/v1/restaurants/{us}/menu-items", headers=boi, json={"name": "Huckleberry pie", "price": "6.999", "category": "x"})
    assert r.status_code == 422
    pie = await add_dish(client, boi, us, f"Huckleberry pie {uuid.uuid4().hex[:6]}", "6.99")
    assert pie["price"] == 6.99
    for who, rest, d in ((partner, rid, dish), (boi, us, pie)):
        await client.delete(f"/api/v1/restaurants/{rest}/menu-items/{d['id']}", headers=who)


async def test_soft_delete_keeps_old_orders_name_and_price(client: AsyncClient) -> None:
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid = (await spice_route(client))["id"]
    tag = uuid.uuid4().hex[:6]
    dish = await add_dish(client, partner, rid, f"Kesari Bath {tag}", "70")
    cart = [{"menu_item_id": dish["id"], "quantity": 3}]  # 210: over the restaurant's own minimum (149)
    q = await quote(client, cust, rid, cart)
    assert q.status_code == 200, q.text
    r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": cart, "payment_method": "upi", "quote_token": q.json()["token"], "delivery_address": ADDRESS})
    assert r.status_code == 201, r.text
    order = r.json()
    assert (await client.delete(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner)).status_code == 204
    assert dish["name"] not in await public_items(client, rid)
    r = await quote(client, cust, rid, cart)
    assert r.status_code == 422 and "no longer on the menu" in r.text
    assert (await client.delete(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner)).status_code == 404
    kept = (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()
    line = next(i for i in kept["items"] if i["menu_item_id"] == dish["id"])
    assert (line["name"], line["unit_price"], line["quantity"]) == (dish["name"], 70.0, 3)
    # the row is still there, marked deleted; the history says so
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        row = (await db.execute(text("SELECT name, price, deleted_at FROM menu_items WHERE id = :i"), {"i": dish["id"]})).one()
    assert row[0] == dish["name"] and str(row[1]) == "70.00" and row[2] is not None
    assert (await history(client, partner, rid, dish["id"]))[0]["action"] == "deleted"


async def test_categories_add_rename_reorder_hide_and_schedule(client: AsyncClient) -> None:
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid = (await spice_route(client))["id"]
    tag = uuid.uuid4().hex[:6]
    base = f"/api/v1/restaurants/{rid}"
    a = (await client.post(f"{base}/categories", headers=partner, json={"name": f"Breakfast {tag}"})).json()
    assert (await client.post(f"{base}/categories", headers=partner, json={"name": f"breakfast {tag}"})).status_code == 409
    dish = await add_dish(client, partner, rid, f"Upma {tag}", "60", category_id=a["id"])
    assert dish["category"] == f"Breakfast {tag}"
    # rename: its dishes follow
    r = await client.put(f"{base}/categories/{a['id']}", headers=partner, json={"name": f"Morning {tag}"})
    assert r.status_code == 200 and r.json()["name"] == f"Morning {tag}"
    menu = (await client.get(f"{base}/menu")).json()
    assert f"Upma {tag}" in [i["name"] for c in menu["categories"] if c["name"] == f"Morning {tag}" for i in c["items"]]
    # reorder: the new category first
    manage = (await client.get(f"{base}/menu/manage", headers=partner)).json()
    ids = [c["id"] for c in manage["categories"]]
    new_order = [a["id"], *[i for i in ids if i != a["id"]]]
    assert (await client.put(f"{base}/categories-order", headers=partner, json={"category_ids": ids[:-1]})).status_code == 422
    r = await client.put(f"{base}/categories-order", headers=partner, json={"category_ids": new_order})
    assert r.status_code == 200, r.text
    assert (await client.get(f"{base}/menu")).json()["categories"][0]["name"] == f"Morning {tag}"
    hist = (await client.get(f"{base}/menu/history", headers=partner, params={"limit": 5})).json()["changes"]
    assert any(c["action"] == "reordered" for c in hist)
    await client.put(f"{base}/categories-order", headers=partner, json={"category_ids": ids})  # back
    # schedule: a window that isn't now (the hour after the next one, local time)
    loc = (await client.get(f"{base}/availability")).json()["local_time"]
    hour = (int(loc[11:13]) + 2) % 24
    window = {"available_from": f"{hour:02d}:00", "available_until": f"{(hour + 1) % 24:02d}:00"}
    assert (await client.put(f"{base}/categories/{a['id']}", headers=partner, json={"available_from": "07:00"})).status_code == 422
    r = await client.put(f"{base}/categories/{a['id']}", headers=partner, json=window)
    assert r.status_code == 200 and r.json()["available_from"] == window["available_from"]
    item = (await public_items(client, rid))[f"Upma {tag}"]
    assert item["available_now"] is False and item["schedule"] == {"from": window["available_from"], "until": window["available_until"]}
    r = await quote(client, cust, rid, [{"menu_item_id": dish["id"], "quantity": 1}])
    assert r.status_code == 422 and "is served" in r.text
    # a window around now: orderable
    now_h = int(loc[11:13])
    r = await client.put(f"{base}/categories/{a['id']}", headers=partner,
                         json={"available_from": f"{now_h:02d}:00", "available_until": f"{(now_h + 2) % 24:02d}:00"})
    assert (await public_items(client, rid))[f"Upma {tag}"]["available_now"] is True
    assert (await quote(client, cust, rid, [{"menu_item_id": dish["id"], "quantity": 1}])).status_code == 200
    # hide: gone from customers' menu, can't be ordered; the editor still sees it
    r = await client.put(f"{base}/categories/{a['id']}", headers=partner, json={"is_active": False, "available_from": None, "available_until": None})
    assert r.status_code == 200 and r.json()["is_active"] is False and r.json()["available_from"] is None
    assert f"Upma {tag}" not in await public_items(client, rid)
    assert (await quote(client, cust, rid, [{"menu_item_id": dish["id"], "quantity": 1}])).status_code == 422
    manage = (await client.get(f"{base}/menu/manage", headers=partner)).json()
    assert any(i["name"] == f"Upma {tag}" for i in manage["items"]) and any(c["id"] == a["id"] and not c["is_active"] for c in manage["categories"])
    await client.delete(f"{base}/menu-items/{dish['id']}", headers=partner)


async def test_options_with_prices_required_and_limits(client: AsyncClient) -> None:
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid = (await spice_route(client))["id"]
    tag = uuid.uuid4().hex[:6]
    base = f"/api/v1/restaurants/{rid}"
    dish = await add_dish(client, partner, rid, f"Thali {tag}", "150")
    r = await client.post(f"{base}/option-groups", headers=partner, json={"name": f"Size {tag}", "min_picks": 1, "max_picks": 1,
                          "options": [{"name": "Mini", "price": "0"}, {"name": "Full", "price": "50.5"}]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PRICE_RULE"
    size = (await client.post(f"{base}/option-groups", headers=partner, json={"name": f"Size {tag}", "min_picks": 1, "max_picks": 1,
                              "options": [{"name": "Mini", "price": "0"}, {"name": "Full", "price": "50"}]})).json()
    extras = (await client.post(f"{base}/option-groups", headers=partner, json={"name": f"Extras {tag}", "min_picks": 0, "max_picks": 2,
                                "options": [{"name": "Papad", "price": "10"}, {"name": "Sweet", "price": "30"}, {"name": "Curd", "price": "20"}]})).json()
    r = await client.put(f"{base}/menu-items/{dish['id']}/option-groups", headers=partner, json={"group_ids": [size["id"], extras["id"]]})
    assert r.status_code == 200, r.text
    opt = lambda g, n: {"group": g["id"], "option": next(o["id"] for o in g["options"] if o["name"] == n)}  # noqa: E731
    r = await quote(client, cust, rid, [{"menu_item_id": dish["id"], "quantity": 2, "options": [opt(size, "Full"), opt(extras, "Papad"), opt(extras, "Sweet")]}])
    assert r.status_code == 200, r.text
    assert food(r.json()) == "480.00"  # (150 + 50 + 10 + 30) x 2
    r = await quote(client, cust, rid, [{"menu_item_id": dish["id"], "quantity": 1, "options": [opt(extras, "Papad")]}])
    assert r.status_code == 422 and "choose" in r.text.lower()  # Size is required
    r = await quote(client, cust, rid, [{"menu_item_id": dish["id"], "quantity": 1, "options": [opt(size, "Mini"), opt(extras, "Papad"), opt(extras, "Sweet"), opt(extras, "Curd")]}])
    assert r.status_code == 422 and "at most 2" in r.text
    # change an option's price: in the history
    r = await client.put(f"{base}/option-groups/{extras['id']}", headers=partner, json={"name": f"Extras {tag}", "min_picks": 0, "max_picks": 2,
                         "options": [{**o, "price": "15" if o["name"] == "Papad" else o["price"]} for o in extras["options"]]})
    assert r.status_code == 200, r.text
    rows = await history(client, partner, rid, extras["id"])
    assert rows[0]["entity"] == "options" and "Papad +15.00" in rows[0]["changes"][0]["new"]
    for g in (size, extras):
        await client.delete(f"{base}/option-groups/{g['id']}", headers=partner)
    await client.delete(f"{base}/menu-items/{dish['id']}", headers=partner)


async def test_dish_search_finds_new_and_renamed_dishes(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    rid = (await spice_route(client))["id"]
    tag = uuid.uuid4().hex[:6]
    dish = await add_dish(client, partner, rid, f"Pesarattu {tag}", "90")

    async def found(word: str) -> list[str]:
        r = await client.get("/api/v1/discover/search", params={"q": word, "lat": HYD[0], "lng": HYD[1]})
        assert r.status_code == 200, r.text
        return [d["name"] for d in r.json()["dishes"]]

    assert f"Pesarattu {tag}" in await found(f"pesarattu {tag}")
    await client.put(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner, json={"name": f"MLA Pesarattu {tag}"})
    assert f"MLA Pesarattu {tag}" in await found(f"mla pesarattu {tag}")
    await client.delete(f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}", headers=partner)
    assert await found(f"pesarattu {tag}") == []


async def test_a_held_price_is_honoured_and_an_expired_one_is_priced_again(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The quote holds the price for 10 minutes: the restaurant raising it meanwhile doesn't change the order.
    After the hold, the order is refused (QUOTE_INVALID) and a new quote has the new price."""
    from datetime import timedelta

    from core_api.modules.pricing.service import quotes as Q

    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid = (await spice_route(client))["id"]
    dish = await add_dish(client, partner, rid, f"Pongal {uuid.uuid4().hex[:6]}", "100")
    cart = [{"menu_item_id": dish["id"], "quantity": 2}]  # 200: over the restaurant's own minimum (149)
    held = (await quote(client, cust, rid, cart)).json()
    assert food(held) == "200.00" and held["items"][0]["unit_price"] == "100.00"
    url = f"/api/v1/restaurants/{rid}/menu-items/{dish['id']}"
    assert (await client.put(url, headers=partner, json={"price": "120"})).status_code == 200
    r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": cart, "payment_method": "upi", "quote_token": held["token"], "delivery_address": ADDRESS})
    assert r.status_code == 201, r.text
    assert r.json()["items"][0]["unit_price"] == 100.0 and r.json()["subtotal"] == 200.0  # the held price

    monkeypatch.setattr(Q, "QUOTE_TTL", timedelta(seconds=1))
    short = (await quote(client, cust, rid, cart)).json()
    assert food(short) == "240.00"
    assert (await client.put(url, headers=partner, json={"price": "130"})).status_code == 200
    await asyncio.sleep(2.2)  # the hold is over
    r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": cart, "payment_method": "upi", "quote_token": short["token"], "delivery_address": ADDRESS})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "QUOTE_INVALID", r.text
    again = (await quote(client, cust, rid, cart)).json()  # priced again: the new price
    assert food(again) == "260.00" and again["items"][0]["unit_price"] == "130.00"
    await client.delete(url, headers=partner)
