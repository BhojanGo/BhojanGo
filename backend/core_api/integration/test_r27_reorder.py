"""R27 on Postgres: "Order again" with options and add-ons. R26: on a delivered order it failed
with "We couldn't add this order to your bag". The same options and quantities come back as picks
the quote accepts; an item sold out and an add-on no longer offered are named, and the rest added."""
import os
import uuid

import pytest
from httpx import AsyncClient

from core_api.integration.test_account import sign_up
from core_api.integration.test_orders_flow import client, pay  # noqa: F401 - fixture
from core_api.integration.test_report_problem import delivered

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
WHERE = {"lat": 17.4483, "lng": 78.3915}


async def menu(client: AsyncClient) -> tuple[dict, dict]:  # noqa: F811
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    m = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    return rest, {i["name"]: i for c in m["categories"] for i in c["items"]}


def pick(item: dict, group: str, option: str) -> dict:
    g = next(x for x in item["option_groups"] if x["name"] == group)
    return {"group": g["id"], "option": next(o["id"] for o in g["options"] if o["name"] == option)}


async def set_flags(sql: str, **params: object) -> None:
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text(sql), params)
        await db.commit()


async def test_order_again_keeps_options_and_names_what_changed(client: AsyncClient) -> None:  # noqa: F811
    h = await sign_up(client)
    rest, items = await menu(client)
    chicken, veg = items["Chicken Dum Biryani"], items["Veg Dum Biryani"]
    picks = [pick(chicken, "Size", "Family · serves 3"), pick(chicken, "Spice", "Hot"), pick(chicken, "Add-ons", "Extra raita")]
    cart = [{"menu_item_id": chicken["id"], "quantity": 2, "options": picks}, {"menu_item_id": veg["id"], "quantity": 1}]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rest["id"], "items": cart, "deliver_to": WHERE})
    assert q.status_code == 200, q.text
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q.json()["token"],
        "delivery_address": {"street": "Flat 302, Road 36", "city": "Hyderabad", "state": "Telangana", "zip": "500081",
                             "country": "IN", **WHERE}})
    assert r.status_code == 201, r.text
    order = r.json()
    await pay(client, h, order)
    await delivered(order["id"])

    out = (await client.post(f"/api/v1/orders/{order['id']}/reorder", headers=h)).json()
    assert out["unavailable"] == [] and out["problems"] == []
    lines = {i["name"]: i for i in out["items"]}
    assert lines["Chicken Dum Biryani"]["quantity"] == 2 and lines["Veg Dum Biryani"]["quantity"] == 1
    assert sorted((p["group"], p["option"]) for p in lines["Chicken Dum Biryani"]["options"]) == sorted((p["group"], p["option"]) for p in picks)
    again = [{k: i[k] for k in ("menu_item_id", "quantity")} | {"options": [{"group": p["group"], "option": p["option"]} for p in i["options"]]}
             for i in out["items"]]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rest["id"], "items": again, "deliver_to": WHERE})
    assert q.status_code == 200, q.text  # the bag it gives quotes as it is

    raita = pick(chicken, "Add-ons", "Extra raita")["option"]
    await set_flags("UPDATE options SET is_available = false WHERE id = CAST(:o AS uuid)", o=raita)
    await set_flags("UPDATE menu_items SET sold_out_until = now() + interval '1 hour' WHERE id = CAST(:i AS uuid)", i=veg["id"])
    try:
        out = (await client.post(f"/api/v1/orders/{order['id']}/reorder", headers=h)).json()
        assert [i["name"] for i in out["items"]] == ["Chicken Dum Biryani"]
        assert {p["option"] for p in out["items"][0]["options"]} == {p["option"] for p in picks} - {raita}
        assert out["unavailable"] == ["Veg Dum Biryani"]
        assert {(p["item"], p["reason"], p["option"]) for p in out["problems"]} == {
            ("Chicken Dum Biryani", "option_gone", "Extra raita"), ("Veg Dum Biryani", "sold_out", None)}
    finally:
        await set_flags("UPDATE options SET is_available = true WHERE id = CAST(:o AS uuid)", o=raita)
        await set_flags("UPDATE menu_items SET sold_out_until = NULL WHERE id = CAST(:i AS uuid)", i=veg["id"])
