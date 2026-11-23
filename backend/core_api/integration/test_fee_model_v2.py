"""R29 fee model v2 on a migrated, seeded Postgres: a Boise order snapshots the fee settings (each inherited from the
USA), the admin Fees screen shows each level's effective value and source, a Boise change needs a second admin and
is audited (who, when, old -> new), and a change after an order is placed never alters that order (D)."""
import os
from decimal import ROUND_HALF_UP, Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login
from core_api.integration.test_tax import client, menu, place  # noqa: F401 - fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"
C = Decimal("0.01")


async def boise_quote(client: AsyncClient, h: dict) -> tuple[str, list[dict], dict]:  # noqa: F811
    address = (await client.get("/api/v1/me/addresses", headers=h)).json()[0]
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Boise Bowl Co.")
    rid, items = await menu(client, rest["slug"])
    cart = [{"menu_item_id": items["Teriyaki Chicken Bowl"], "quantity": 2}]
    r = await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": cart, "deliver_to": {"address_id": address["id"]}, "tip": "2"})
    assert r.status_code == 200, r.text
    return rid, cart, r.json()


def line(q: dict, code: str) -> Decimal:
    return sum((Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] == code), Decimal(0))


def field(level: dict, name: str) -> dict:
    return next(f for f in level["fields"] if f["field"] == name)


async def test_boise_order_fees_snapshot_admin_levels_and_a_later_change(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.boi@example.com")
    maker = await login(client, "cm.us@example.com", ADMIN)
    checker = await login(client, "finance.us@example.com", ADMIN)
    ops = await login(client, "ops.boi@example.com", ADMIN)

    # The bill: the platform fee is 10% of food (at least $0.99); the partner gets the delivery fee and the tip.
    rid, cart, q = await boise_quote(client, cust)
    food = line(q, "food")
    fee = line(q, "platform_fee")
    assert fee == max(Decimal("0.99"), (food * Decimal("0.10")).quantize(C, rounding=ROUND_HALF_UP))
    assert "service_fee" not in {ln["code"] for ln in q["lines"]}
    order = await place(client, cust, rid, cart, q, "US")
    total, tip = Decimal(str(order["total"])), Decimal("2")
    card = ((total - tip) * Decimal("0.029")).quantize(C, rounding=ROUND_HALF_UP) + Decimal("0.30")
    snap = (await client.get(f"/api/v1/pricing/orders/{order['id']}/snapshot", headers=ops)).json()
    split = snap["split"]
    assert Decimal(split["card_fee"]) == card
    assert Decimal(split["restaurant"]) == food - card  # commission 0%
    assert Decimal(split["rider"]) >= line(q, "delivery_fee") + tip
    assert Decimal(split["detail"]["delivery_fee_to_partner"]) == line(q, "delivery_fee")
    fs = snap["fee_settings"]
    assert fs["platform_fee_pct"]["value"] == {"percent": "10"} and fs["platform_fee_pct"]["source"]["level"] == "country"
    assert fs["min_platform_fee"]["value"] == {"amount": "0.99"}
    assert fs["restaurant_commission_pct"]["value"] == {"percent": "0"}
    assert fs["card_fee_estimate"]["value"] == {"card": {"percent": "2.9", "fixed": "0.30"}}  # R30: per method
    assert fs["delivery_fee"]["value"] == {"base": "3.00", "per_unit": "1.00"} and fs["delivery_fee"]["source"]["level"] == "city"
    before = {k: snap[k] for k in ("total", "lines", "split", "fee_settings")}

    # Admin Fees: every level shows the effective value and where it comes from.
    for level, sid, name in (("country", "US", "United States"), ("region", "US-ID", "Idaho"), ("city", "US-ID-BOI", "Boise"),
                             ("restaurant", rid, "Boise Bowl Co.")):
        got = (await client.get("/api/v1/rules/fees", headers=maker, params={"level": level, "scope_id": sid})).json()
        pf = field(got, "platform_fee_pct")
        assert got["name"] == name and pf["effective"] == {"percent": "10"}, got
        assert pf["source"]["level"] == "country" and pf["inherited"] is (level != "country")
    us = (await client.get("/api/v1/rules/fees", headers=maker, params={"level": "country", "scope_id": "US"})).json()
    assert field(us, "platform_fee_pct")["own"]["value"] == {"percent": "10"}
    assert (await client.get("/api/v1/rules/fees", headers=await login(client, "ops.hyd@example.com", ADMIN),
                             params={"level": "city", "scope_id": "US-ID-BOI"})).status_code == 403

    # Boise 12%: a money rule, so it waits for a second admin.
    r = await client.post("/api/v1/rules/fees", headers=maker, json={
        "level": "city", "scope_id": "US-ID-BOI", "field": "platform_fee_pct", "value": {"percent": 12}})
    assert r.status_code == 201 and r.json()["status"] == "pending_approval", r.text
    rule_id = r.json()["rule_id"]
    try:
        boise = (await client.get("/api/v1/rules/fees", headers=maker, params={"level": "city", "scope_id": "US-ID-BOI"})).json()
        assert field(boise, "platform_fee_pct")["effective"] == {"percent": "10"}  # not until approved
        assert [p["status"] for p in field(boise, "platform_fee_pct")["pending"]] == ["pending_approval"]
        assert (await client.post(f"/api/v1/rules/{rule_id}/approve", headers=maker, json={})).status_code == 409
        r = await client.post(f"/api/v1/rules/{rule_id}/approve", headers=checker, json={"note": "Boise launch price"})
        assert r.status_code == 200 and r.json()["status"] == "published", r.text

        boise = (await client.get("/api/v1/rules/fees", headers=maker, params={"level": "city", "scope_id": "US-ID-BOI"})).json()
        pf = field(boise, "platform_fee_pct")
        assert pf["effective"] == {"percent": "12"} and pf["inherited"] is False and pf["source"]["name"] == "Boise"
        assert field(boise, "min_platform_fee")["source"]["name"] == "United States"  # the minimum still inherits
        kitchen = (await client.get("/api/v1/rules/fees", headers=maker, params={"level": "restaurant", "scope_id": rid})).json()
        assert field(kitchen, "platform_fee_pct")["source"]["name"] == "Boise"
        audit = [h for h in boise["history"] if h["field"] == "platform_fee_pct"]
        assert {h["action"] for h in audit} >= {"rule.created", "rule.submitted", "rule.approved"}
        approved = next(h for h in audit if h["action"] == "rule.approved")
        assert approved["new"] == {"percent": "12"} and approved["who"] == "USA Finance"
        created = next(h for h in audit if h["action"] == "rule.created")
        assert created["old"] is None and created["who"] == "USA Country Manager"

        # A new quote uses 12%; the order placed before keeps its numbers exactly (D).
        _, _, q2 = await boise_quote(client, cust)
        assert line(q2, "platform_fee") == max(Decimal("0.99"), (food * Decimal("0.12")).quantize(C, rounding=ROUND_HALF_UP))
        after = (await client.get(f"/api/v1/pricing/orders/{order['id']}/snapshot", headers=ops)).json()
        assert {k: after[k] for k in before} == before
        again = (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()
        assert Decimal(str(again["total"])) == total
        bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=cust)).json()
        assert Decimal(bill["total"]) == total
        assert next(Decimal(ln["amount"]) for ln in bill["lines"] if ln["code"] == "platform_fee") == fee
    finally:
        # Boise inherits the USA's 10% again (the version stays in the history).
        r = await client.delete("/api/v1/rules/fees", headers=checker,
                                params={"level": "city", "scope_id": "US-ID-BOI", "field": "platform_fee_pct"})
        assert r.status_code in (200, 404), r.text
    boise = (await client.get("/api/v1/rules/fees", headers=maker, params={"level": "city", "scope_id": "US-ID-BOI"})).json()
    assert field(boise, "platform_fee_pct")["effective"] == {"percent": "10"} and field(boise, "platform_fee_pct")["inherited"]


async def test_fee_values_are_validated(client: AsyncClient) -> None:  # noqa: F811
    maker = await login(client, "cm.us@example.com", ADMIN)
    for value in ({"percent": 120}, {"percent": -1}):
        r = await client.post("/api/v1/rules/fees", headers=maker, json={
            "level": "region", "scope_id": "US-ID", "field": "platform_fee_pct", "value": value})
        assert r.status_code == 422, r.text
    r = await client.post("/api/v1/rules/fees", headers=maker, json={
        "level": "region", "scope_id": "US-ID", "field": "card_fee_estimate", "value": {"percent": 50, "fixed": "0.30"}})
    assert r.status_code == 422, r.text
