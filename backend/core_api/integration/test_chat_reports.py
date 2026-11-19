"""R19 on Postgres (Apple 1.2): in quick messages, either side reports a message from
the other (a "chat_report" ticket in the support console with the conversation) and
blocks the other person (their messages are hidden from and not pushed to the
blocker; unblocking shows them again)."""
import os
import uuid

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import assign, client, login, move, new_order, outbox_types, pay  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_report_and_block_in_quick_messages(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)
    oid = order["id"]
    url = f"/api/v1/orders/{oid}/messages"
    await pay(client, cust, order)
    partner = await login(client, "partner.hyd@example.com")
    for s in ("accepted", "preparing", "almost_ready", "ready"):
        assert (await move(client, partner, oid, s)).status_code == 200
    rider = await login(client, "rider1.hyd@example.com")
    assert (await assign(client, oid, rider)).status_code == 200

    theirs = (await client.post(url, headers=rider, json={"text": "Rude words here"})).json()
    mine = (await client.post(url, headers=cust, json={"preset": "ring_bell"})).json()
    try:
        # Only the other side's messages, only by the order's people.
        r = await client.post(f"{url}/{mine['id']}/report", headers=cust, json={"reason": "spam"})
        assert r.status_code == 422
        assert (await client.post(f"{url}/{uuid.uuid4()}/report", headers=cust, json={"reason": "spam"})).status_code == 404
        other = await login(client, "customer2.hyd@example.com")
        assert (await client.post(f"{url}/{theirs['id']}/report", headers=other, json={"reason": "spam"})).status_code == 404
        assert (await client.post(f"{url}/block", headers=other)).status_code == 404

        r = await client.post(f"{url}/{theirs['id']}/report", headers=cust,
                              json={"reason": "abusive", "note": "Not nice", "block": True})
        assert r.status_code == 201 and r.json()["blocked"] is True, r.text
        tid = r.json()["ticket_id"]
        again = await client.post(f"{url}/{theirs['id']}/report", headers=cust, json={"reason": "abusive"})
        assert again.json()["ticket_id"] == tid  # the same open report

        support = await login(client, "support.hyd@example.com", "BhojanGoAdmin1")
        t = next(x for x in (await client.get("/api/v1/ops/tickets", headers=support, params={"scope": "IN-TG-HYD"})).json()
                 if x["id"] == tid)
        assert t["kind"] == "chat_report" and t["topic"] == "abusive" and t["note"] == "Not nice" and t["order_id"] == oid
        assert t["requester_role"] == "customer" and t["details"]["reported_role"] == "rider"
        assert t["details"]["message_text"] == "Rude words here"
        assert [m["role"] for m in t["details"]["conversation"]] == ["rider", "customer"]

        # Blocked: the rider's messages are hidden from the customer and not pushed to them.
        before = (await outbox_types(oid)).count("order.message")
        assert (await client.post(url, headers=rider, json={"preset": "outside"})).status_code == 201
        assert (await outbox_types(oid)).count("order.message") == before
        seen = (await client.get(url, headers=cust)).json()
        assert seen["blocked"] is True and [m["sender_role"] for m in seen["messages"]] == ["customer"]
        assert (await client.get(url, headers=rider)).json()["blocked"] is False  # the rider still reads both
        assert len((await client.get(url, headers=rider)).json()["messages"]) == 3
        # The customer can still write; the rider gets it.
        assert (await client.post(url, headers=cust, json={"text": "Leave it at the gate"})).status_code == 201
        assert (await outbox_types(oid)).count("order.message") == before + 1

        r = await client.delete(f"{url}/block", headers=cust)
        assert r.status_code == 200 and r.json()["blocked"] is False
        seen = (await client.get(url, headers=cust)).json()
        assert seen["blocked"] is False and len(seen["messages"]) == 4
        # Blocking without a report works too (from the chat's header).
        assert (await client.post(f"{url}/block", headers=rider)).json()["blocked"] is True
        assert (await client.get(url, headers=rider)).json()["blocked"] is True
    finally:  # the seeded people meet again in other tests
        await client.delete(f"{url}/block", headers=cust)
        await client.delete(f"{url}/block", headers=rider)
