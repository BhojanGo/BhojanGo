"""The web's account area on Postgres: order history filters, order again,
the receipt PDF, favourites, the data export, and account deletion keeping
orders without the personal details. Each test signs up its own customer, so
the seeded customers' history doesn't get in the way."""
import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, new_order, pay  # noqa: F401
from core_api.integration.test_report_problem import chai_order, delivered
from core_api.modules.orders.tests.test_receipt import pdf_text

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

CARD = {"provider": "fake", "brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": date.today().year + 2}


async def sign_up(client: AsyncClient, name: str = "Asha Rao") -> dict:  # noqa: F811
    from core_api.modules.identity.tests.signin import email_sign_up

    t = await email_sign_up(client, f"acct-{uuid.uuid4().hex[:10]}@example.com", "BhojanGo-test-pw1", country="IN",
                            full_name=name)
    h = {"Authorization": f"Bearer {t['access_token']}"}
    r = await client.patch("/api/v1/users/me", headers=h, json={"preferred_locale": "te-IN"})
    assert r.status_code == 200, r.text
    return h


async def spice_and_biryani(client: AsyncClient) -> tuple[dict, dict]:  # noqa: F811
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    return rest, next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")


async def history(client: AsyncClient, h: dict, **params) -> list[dict]:  # type: ignore[no-untyped-def]  # noqa: F811
    r = await client.get("/api/v1/orders", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def test_order_history_search_and_filters(client: AsyncClient) -> None:  # noqa: F811
    h = await sign_up(client)
    biryani = await new_order(client, h)                       # delivered
    await pay(client, h, biryani)
    await delivered(biryani["id"])
    chai_waiting, _ = await chai_order(client, h, 6)          # active: waiting for payment
    chai_cancelled, _ = await chai_order(client, h, 5)        # cancelled
    r = await client.post(f"/api/v1/orders/{chai_cancelled['id']}/cancel", headers=h, json={"reason": "customer_cancelled"})
    assert r.status_code == 200, r.text

    everything = await history(client, h)
    assert [o["id"] for o in everything] == [chai_cancelled["id"], chai_waiting["id"], biryani["id"]]  # newest first
    b = everything[-1]
    assert b["restaurant_name"] == "Spice Route Kitchen" and b["restaurant_slug"] == "spice-route-kitchen-madhapur"
    assert b["items_summary"] == "2 × Veg Dum Biryani" and b["currency"] == "INR" and b["status"] == "delivered"
    assert b["total"] > 0 and b["created_at"] and b["items"]  # the old shape is still there

    ids = lambda rows: {o["id"] for o in rows}  # noqa: E731
    assert ids(await history(client, h, q="biryani")) == {biryani["id"]}            # an item's name
    assert ids(await history(client, h, q="charminar CHAI")) == {chai_waiting["id"], chai_cancelled["id"]}  # the kitchen's
    assert await history(client, h, q="%") == []                                      # a literal %, not a wildcard
    assert ids(await history(client, h, status="delivered")) == {biryani["id"]}
    assert ids(await history(client, h, status="cancelled")) == {chai_cancelled["id"]}
    assert ids(await history(client, h, status="active")) == {chai_waiting["id"]}
    assert ids(await history(client, h, status=["delivered", "cancelled"])) == {biryani["id"], chai_cancelled["id"]}
    assert ids(await history(client, h, restaurant_id=biryani["restaurant_id"])) == {biryani["id"]}

    today = datetime.now(UTC).date()
    assert len(await history(client, h, **{"from": today.isoformat(), "to": today.isoformat()})) == 3
    assert await history(client, h, **{"from": (today + timedelta(days=1)).isoformat()}) == []
    assert await history(client, h, to=(today - timedelta(days=1)).isoformat()) == []
    r = await client.get("/api/v1/orders", headers=h, params={"limit": 1, "page": 2, "status": "active"})
    assert r.json()["total"] == 1 and r.json()["items"] == []
    for bad in ({"status": "lost"}, {"from": today.isoformat(), "to": (today - timedelta(days=1)).isoformat()}):
        assert (await client.get("/api/v1/orders", headers=h, params=bad)).status_code == 422


async def test_order_again_uses_todays_menu(client: AsyncClient) -> None:  # noqa: F811
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    h = await sign_up(client)
    order = await new_order(client, h)
    await pay(client, h, order)
    await delivered(order["id"])
    rest, biryani = await spice_and_biryani(client)

    r = await client.post(f"/api/v1/orders/{order['id']}/reorder", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["restaurant"] == {"id": rest["id"], "slug": "spice-route-kitchen-madhapur", "name": "Spice Route Kitchen",
                                 "currency": "INR"}
    assert out["items"] == [{"menu_item_id": biryani["id"], "name": "Veg Dum Biryani", "quantity": 2, "options": [],
                             "price": float(biryani["price"]), "available": True}]
    assert out["unavailable"] == []
    # The bag it gives quotes as it is.
    q = await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rest["id"], "items": [{k: i[k] for k in ("menu_item_id", "quantity", "options")} for i in out["items"]],
        "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    assert q.status_code == 200, q.text

    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE menu_items SET sold_out_until = now() + interval '1 hour' WHERE id = :i"), {"i": biryani["id"]})
        await db.commit()
    try:
        out = (await client.post(f"/api/v1/orders/{order['id']}/reorder", headers=h)).json()
        assert out["items"] == [] and out["unavailable"] == ["Veg Dum Biryani"]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE menu_items SET sold_out_until = NULL WHERE id = :i"), {"i": biryani["id"]})
            await db.commit()

    other = await sign_up(client)
    assert (await client.post(f"/api/v1/orders/{order['id']}/reorder", headers=other)).status_code == 404


async def test_receipt_pdf_is_a_tax_invoice_in_india(client: AsyncClient) -> None:  # noqa: F811
    from core_api.modules.orders.service import receipt as R

    h = await sign_up(client, "Ravi Kumar")
    order = await new_order(client, h)
    url = f"/api/v1/orders/{order['id']}/receipt.pdf"
    r = await client.get(url, headers=h)
    assert r.status_code == 409  # not paid yet
    await pay(client, h, order)

    r = await client.get(url, headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    number = R.invoice_number(uuid.UUID(order["id"]), datetime.fromisoformat(order["created_at"]), "IN")
    assert number.startswith("BG-IN-") and f'filename="{number}.pdf"' in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF-")
    text = pdf_text(r.content)
    bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=h)).json()
    for want in ("Tax invoice", number, R.money(order["total"], "INR"), "Spice Route Kitchen", "FSSAI", "Ravi Kumar",
                 "Flat 302", "Veg Dum Biryani", *[ln["label"] for ln in bill["lines"]]):
        assert want in text, want
    taxes = [ln for ln in bill["lines"] if ln["code"] == "tax" and (ln.get("detail") or {}).get("rate_percent")]
    assert taxes  # GST, each with its rate
    for ln in taxes:
        assert f"{ln['label']} @ {R._pct(ln['detail']['rate_percent'])}" in text

    other = await sign_up(client)
    assert (await client.get(url, headers=other)).status_code == 404


async def test_favourites(client: AsyncClient) -> None:  # noqa: F811
    h = await sign_up(client)
    rest, biryani = await spice_and_biryani(client)
    for _ in range(2):  # idempotent
        assert (await client.put(f"/api/v1/me/favourites/restaurant/{rest['id']}", headers=h)).status_code == 204
    assert (await client.put(f"/api/v1/me/favourites/item/{biryani['id']}", headers=h)).status_code == 204
    assert (await client.put(f"/api/v1/me/favourites/item/{uuid.uuid4()}", headers=h)).status_code == 404
    assert (await client.put(f"/api/v1/me/favourites/restaurant/{biryani['id']}", headers=h)).status_code == 404  # wrong kind
    assert (await client.put(f"/api/v1/me/favourites/dish/{biryani['id']}", headers=h)).status_code == 422

    fav = (await client.get("/api/v1/me/favourites", headers=h)).json()
    assert len(fav["restaurants"]) == 1 and len(fav["items"]) == 1
    r = fav["restaurants"][0]
    assert (r["id"], r["slug"], r["name"], r["currency"], r["city"], r["country"]) == (
        rest["id"], "spice-route-kitchen-madhapur", "Spice Route Kitchen", "INR", "Hyderabad", "IN")
    assert {"cuisine_types", "cover_url", "rating", "delivery_time_min", "delivery_time_max", "delivery_fee"} <= set(r)
    i = fav["items"][0]
    assert (i["id"], i["name"], i["price"], i["currency"]) == (biryani["id"], "Veg Dum Biryani", float(biryani["price"]), "INR")
    # With its city and country: the dish opens its kitchen's page even when the kitchen isn't saved (R9).
    assert i["restaurant"] == {"id": rest["id"], "slug": "spice-route-kitchen-madhapur", "name": "Spice Route Kitchen",
                               "city": "Hyderabad", "country": "IN"}

    assert (await client.delete(f"/api/v1/me/favourites/restaurant/{rest['id']}", headers=h)).status_code == 204
    assert (await client.delete(f"/api/v1/me/favourites/restaurant/{rest['id']}", headers=h)).status_code == 204
    fav = (await client.get("/api/v1/me/favourites", headers=h)).json()
    assert fav["restaurants"] == [] and len(fav["items"]) == 1


async def test_data_export_has_everything_of_mine_and_nothing_of_anyone_else(client: AsyncClient) -> None:  # noqa: F811
    import json

    h = await sign_up(client, "Meena Iyer")
    order = await new_order(client, h)
    await pay(client, h, order)
    rest, _ = await spice_and_biryani(client)
    await client.post("/api/v1/me/addresses", headers=h, json={"street": "Flat 302", "city": "Hyderabad",
                                                                "delivery_notes": "Ring twice"})
    token = f"pm_fake_export{uuid.uuid4().hex[:6]}"
    assert (await client.post("/api/v1/me/payment-methods", headers=h, json={**CARD, "provider_token": token})).status_code == 201
    await client.put(f"/api/v1/me/favourites/restaurant/{rest['id']}", headers=h)
    await client.put("/api/v1/me/notification-preferences", headers=h, json={"offers": {"email": True}})

    r = await client.get("/api/v1/me/export", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].startswith('attachment; filename="bhojango-data-')
    data = json.loads(r.content)
    assert set(data) >= {"profile", "addresses", "orders", "payment_methods", "favourites", "notification_preferences",
                         "support_tickets", "refunds_and_problems", "reviews"}
    assert data["profile"]["full_name"] == "Meena Iyer" and data["profile"]["preferred_locale"] == "te-IN"
    assert data["addresses"][0]["delivery_notes"] == "Ring twice"
    o = data["orders"][0]
    assert o["id"] == order["id"] and o["items"] and o["bill"]["lines"] and o["bill"]["currency"] == "INR"
    assert data["payment_methods"][0]["last4"] == "4242" and token not in r.text and "provider_token" not in r.text
    assert data["favourites"]["restaurants"][0]["id"] == rest["id"]
    assert data["notification_preferences"]["offers"]["email"] is True
    # Nobody else: no rider, no kitchen payout split, no rule internals.
    # (as keys: R29's bill has a line whose code is "platform_fee", the customer's own fee)
    for other in ("driver_id", "rider", "restaurant_payout", "platform_fee", "rule_id", "split", "card_fee"):
        assert f'"{other}":' not in r.text, other


async def test_account_deletion_keeps_orders_for_tax_without_personal_details(client: AsyncClient) -> None:  # noqa: F811
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    h = await sign_up(client)
    rest, biryani = await spice_and_biryani(client)
    cart = [{"menu_item_id": biryani["id"], "quantity": 1}]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rest["id"], "items": cart,
                                                                    "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q.json()["token"],
        "special_instructions": "Gate code 4512, ring twice",
        "delivery_address": {"street": "Flat 302, Road 36", "landmark": "Opp. temple", "city": "Hyderabad",
                             "state": "Telangana", "zip": "500081", "country": "IN", "lat": 17.4483, "lng": 78.3915}})
    assert r.status_code == 201, r.text
    order = r.json()
    await pay(client, h, order)
    await client.post("/api/v1/me/payment-methods", headers=h, json={**CARD, "provider_token": f"pm_fake_del{uuid.uuid4().hex[:6]}"})
    await client.put(f"/api/v1/me/favourites/restaurant/{rest['id']}", headers=h)
    await client.put("/api/v1/me/notification-preferences", headers=h, json={"offers": {"sms": True}})
    me = (await client.get("/api/v1/users/me", headers=h)).json()["id"]

    assert (await client.delete("/api/v1/users/me", headers=h)).status_code == 200

    async with AsyncSessionLocal() as db:
        row = (await db.execute(text(
            "SELECT customer_id, total, delivery_address, special_instructions, delivery_lat, delivery_lng "
            "FROM orders WHERE id = :i"), {"i": order["id"]})).one()
        assert str(row.customer_id) == me and float(row.total) == order["total"]  # the order stays, for tax
        assert row.delivery_address == {"street": "", "landmark": None, "city": "Hyderabad", "state": "Telangana",
                                        "zip": "500081", "country": "IN"}
        assert row.special_instructions is None and row.delivery_lat is None and row.delivery_lng is None
        for table in ("payment_methods", "favourites", "notification_preferences", "addresses"):
            n = (await db.execute(text(f"SELECT count(*) FROM {table} WHERE user_id = :u"), {"u": me})).scalar()
            assert n == 0, table


async def test_an_order_priced_before_round_8_reads_delivery_partner_everywhere(client: AsyncClient) -> None:  # noqa: F811
    """R8: a pricing snapshot that still says "Tip for your rider" goes out with today's
    words: the bill (in the customer's language, te-IN), the receipt PDF, the data export
    and the admin snapshot."""
    import json

    from sqlalchemy import text

    from core_api.integration.test_pricing import login as admin_login
    from shared.db import AsyncSessionLocal

    h = await sign_up(client, "Kiran Rao")
    order = await new_order(client, h)
    await pay(client, h, order)
    old = {"code": "tip", "label": "Tip for your rider", "amount": "20.00"}
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE order_pricing_snapshots SET lines = lines || CAST(:ln AS jsonb) WHERE order_id = :o"),
                         {"ln": json.dumps([old]), "o": order["id"]})
        await db.commit()

    bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=h)).json()
    tip = next(ln for ln in bill["lines"] if ln["code"] == "tip")
    assert tip["label"] == "మీ డెలివరీ పార్ట్‌నర్‌కు టిప్" and tip["amount"] == "20.00"  # te-IN, as the customer reads

    pdf = pdf_text((await client.get(f"/api/v1/orders/{order['id']}/receipt.pdf", headers=h)).content)
    assert "Tip for your delivery partner" in pdf and "rider" not in pdf.lower()

    export = (await client.get("/api/v1/me/export", headers=h)).text
    assert "Tip for your rider" not in export

    admin, _ = await admin_login(client, "ops.hyd@example.com", "BhojanGoAdmin1")
    snap = (await client.get(f"/api/v1/pricing/orders/{order['id']}/snapshot", headers=admin)).json()
    assert [ln["label"] for ln in snap["lines"] if ln["code"] == "tip"] == ["Tip for your delivery partner"]
