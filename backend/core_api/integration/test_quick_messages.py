"""B2 on Postgres: the customer and the assigned rider exchange quick messages
while the order is on its way; nobody else sees them and they're hidden after
delivery."""
import os

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import assign, client, login, move, new_order, outbox_types, pay  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_quick_messages_during_the_order(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)
    oid = order["id"]
    url = f"/api/v1/orders/{oid}/messages"
    await pay(client, cust, order)
    partner = await login(client, "partner.hyd@example.com")
    for s in ("accepted", "preparing", "almost_ready", "ready"):
        assert (await move(client, partner, oid, s)).status_code == 200

    # No rider yet: closed.
    r = await client.get(url, headers=cust)
    assert r.status_code == 200 and r.json()["open"] is False and r.json()["presets"] == []
    assert (await client.post(url, headers=cust, json={"preset": "ring_bell"})).status_code == 409

    rider = await login(client, "rider1.hyd@example.com")
    assert (await assign(client, oid, rider)).status_code == 200
    mine = (await client.get(url, headers=cust)).json()
    assert mine["open"] and mine["me"] == "customer" and mine["other_name"] and " " not in mine["other_name"]
    assert {p["key"] for p in mine["presets"]} == {"leave_at_door", "coming_down", "ring_bell", "ask_guard"}
    theirs = (await client.get(url, headers=rider)).json()
    assert theirs["me"] == "rider" and "outside" in {p["key"] for p in theirs["presets"]}

    r = await client.post(url, headers=rider, json={"preset": "at_kitchen"})
    assert r.status_code == 201 and r.json()["text"].startswith("I'm at the kitchen") and r.json()["mine"]
    assert (await client.post(url, headers=rider, json={"preset": "ring_bell"})).status_code == 422  # the customer's
    r = await client.post(url, headers=cust, json={"text": "Gate 2, call 98480 22334"})
    assert r.status_code == 201 and r.json()["text"] == "Gate 2, call •••"

    seen = (await client.get(url, headers=rider)).json()["messages"]
    assert [(m["sender_role"], m["mine"]) for m in seen] == [("rider", True), ("customer", False)]
    assert (await outbox_types(oid)).count("order.message") == 2

    # Nobody else: not another customer, rider or the kitchen, and not an admin.
    for who in (("customer2.hyd@example.com", "BhojanGo123"), ("rider2.hyd@example.com", "BhojanGo123"),
                ("partner.hyd@example.com", "BhojanGo123"), ("ops.hyd@example.com", "BhojanGoAdmin1")):
        h = await login(client, *who)
        assert (await client.get(url, headers=h)).status_code == 404
        assert (await client.post(url, headers=h, json={"text": "hi"})).status_code == 404

    # Delivered: hidden from both sides, and closed.
    assert (await move(client, rider, oid, "picked_up")).status_code == 200
    assert (await move(client, rider, oid, "delivered")).status_code == 200
    for h in (cust, rider):
        r = (await client.get(url, headers=h)).json()
        assert r["open"] is False and r["messages"] == []
    assert (await client.post(url, headers=cust, json={"text": "thanks"})).status_code == 409
