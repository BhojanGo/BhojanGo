"""B3 on Postgres: a kitchen asks for a call back from the tablet; the ticket
shows in the support console for its city (with the number to call), and an
admin who can act resolves it with a note (audited)."""
import os

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
PW = "BhojanGoAdmin1"


async def test_kitchen_callback_reaches_the_support_console(client: AsyncClient) -> None:  # noqa: F811
    partner = await login(client, "partner.hyd@example.com")
    spice = (await client.get("/api/v1/restaurants/mine", headers=partner)).json()[0]["id"]
    url = f"/api/v1/restaurants/{spice}/callback"

    r = await client.post(url, headers=partner, json={"topic": "payout", "note": "Last week's payout looks short"})
    assert r.status_code == 201 and r.json()["status"] == "open", r.text
    tid = r.json()["id"]
    # Asking again while it's open: the same request, with the newer topic.
    again = await client.post(url, headers=partner, json={"topic": "order"})
    assert again.json()["id"] == tid and again.json()["topic"] == "order" and again.json()["note"] == "Last week's payout looks short"
    assert (await client.get(url, headers=partner)).json()["id"] == tid

    # Only the kitchen's owner asks.
    for who in (("partner.boi@example.com", "BhojanGo123"), ("customer1.hyd@example.com", "BhojanGo123"), ("ops.hyd@example.com", PW)):
        assert (await client.post(url, headers=await login(client, *who), json={"topic": "other"})).status_code == 403

    ops = await login(client, "ops.hyd@example.com", PW)
    mine = [t for t in (await client.get("/api/v1/ops/tickets", headers=ops, params={"scope": "IN-TG-HYD"})).json() if t["id"] == tid]
    assert mine and mine[0]["restaurant_name"] == "Spice Route Kitchen" and mine[0]["requester_phone"]
    assert mine[0]["kind"] == "callback" and mine[0]["city"] == "IN-TG-HYD"
    boise = await login(client, "ops.boi@example.com", PW)
    assert tid not in {t["id"] for t in (await client.get("/api/v1/ops/tickets", headers=boise)).json()}
    assert (await client.post(f"/api/v1/ops/tickets/{tid}/resolve", headers=boise, json={"resolution": "x" * 5})).status_code == 404
    viewer = await login(client, "viewer@example.com", PW)
    assert (await client.post(f"/api/v1/ops/tickets/{tid}/resolve", headers=viewer, json={"resolution": "Called"})).status_code == 403

    support = await login(client, "support.hyd@example.com", PW)
    r = await client.post(f"/api/v1/ops/tickets/{tid}/resolve", headers=support, json={"resolution": "Called Ravi; payout was for 6 days"})
    assert r.status_code == 200 and r.json()["status"] == "resolved" and r.json()["resolved_at"]
    assert (await client.post(f"/api/v1/ops/tickets/{tid}/resolve", headers=support, json={"resolution": "again"})).status_code == 409
    assert (await client.get(url, headers=partner)).json() is None
    done = (await client.get("/api/v1/ops/tickets", headers=ops, params={"scope": "IN-TG-HYD", "state": "resolved"})).json()
    assert any(t["id"] == tid and t["resolution"].startswith("Called Ravi") for t in done)

    from sqlalchemy import select

    from core_api.modules.audit.models import AuditLog
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(AuditLog).where(AuditLog.entity_id == tid))).scalars().all()
    assert [a.action for a in rows] == ["ticket.resolved"] and rows[0].scope == "IN-TG-HYD"
