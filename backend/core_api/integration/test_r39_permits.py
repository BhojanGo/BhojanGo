"""R39 item 5 on Postgres: a US restaurant's food permit (number, expiry, upload), an admin's review, going
live only with an approved permit, the reminder 30 days before it expires and the automatic pause after."""
import os
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login, upload  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
PW = "BhojanGoAdmin1"
SAVED = ("status, food_permit_number, food_permit_expires_on, food_permit_document_key, food_permit_status, food_permit_note, "
         "food_permit_reminded_for, paused_reason")


async def _sql(q: str, **p):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(q), p)).all() if q.lstrip().upper().startswith("SELECT") else (await db.execute(text(q), p))
        await db.commit()
        return rows


@pytest.fixture
async def boise():  # type: ignore[no-untyped-def]
    """partner.boi's first restaurant, put back exactly as it was afterwards."""
    (rid,), = await _sql("SELECT r.id FROM restaurants r JOIN users u ON u.id = r.owner_id WHERE u.email = 'partner.boi@example.com' "
                         "ORDER BY r.name LIMIT 1")
    (before,) = await _sql(f"SELECT {SAVED} FROM restaurants WHERE id = :r", r=rid)
    yield str(rid)
    cols = [c.strip() for c in SAVED.split(",")]
    await _sql("UPDATE restaurants SET " + ", ".join(f"{c} = :{c}" for c in cols) + " WHERE id = :r",
               r=rid, **dict(zip(cols, before, strict=True)))


async def test_permit_review_and_going_live(client: AsyncClient, boise: str) -> None:  # noqa: F811
    owner = await login(client, "partner.boi@example.com")
    ops = await login(client, "ops.boi@example.com", PW)
    # A new applicant: no permit yet
    await _sql("UPDATE restaurants SET status = 'pending_approval', food_permit_number = NULL, food_permit_expires_on = NULL, "
               "food_permit_document_key = NULL, food_permit_status = NULL WHERE id = CAST(:r AS uuid)", r=boise)
    a = (await client.get(f"/api/v1/restaurants/{boise}/application", headers=owner)).json()
    step = next(s for s in a["steps"] if s["key"] == "fssai")
    assert step["title"] == "Food permit" and not step["done"] and a["food_permit"]["required"] is True
    r = await client.post(f"/api/v1/restaurants/{boise}/approve", headers=ops)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "FOOD_PERMIT", r.text

    # The owner sends it: an expired one is refused; a valid one waits for review
    key = (await upload(client, owner, "partner_document")).json()["key"]
    until = (date.today() + timedelta(days=400)).isoformat()
    bad = await client.put(f"/api/v1/restaurants/{boise}/food-permit", headers=owner, json={
        "number": "CDH-12345", "expires_on": (date.today() - timedelta(days=1)).isoformat(), "document_key": key})
    assert bad.status_code == 422 and "expired" in bad.json()["detail"]["message"]
    r = await client.put(f"/api/v1/restaurants/{boise}/food-permit", headers=owner, json={
        "number": "CDH-12345", "expires_on": until, "document_key": key})
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["document"], r.text
    a = (await client.get(f"/api/v1/restaurants/{boise}/application", headers=owner)).json()
    assert next(s for s in a["steps"] if s["key"] == "fssai")["done"]
    assert (await client.post(f"/api/v1/restaurants/{boise}/approve", headers=ops)).status_code == 409  # not reviewed yet

    # The admin sees it, opens the upload, turns it down with a reason, then approves the corrected one
    pending = (await client.get("/api/v1/restaurants/admin/permits", headers=ops)).json()
    assert any(p["restaurant_id"] == boise and p["number"] == "CDH-12345" for p in pending), pending
    assert (await client.get("/api/v1/uploads/view", headers=ops, params={"key": key})).status_code == 200
    hyd = await login(client, "ops.hyd@example.com", PW)
    assert all(p["restaurant_id"] != boise for p in (await client.get("/api/v1/restaurants/admin/permits", headers=hyd)).json())
    assert (await client.post(f"/api/v1/restaurants/{boise}/food-permit/review", headers=hyd, json={"decision": "approve"})).status_code == 403
    assert (await client.post(f"/api/v1/restaurants/{boise}/food-permit/review", headers=owner, json={"decision": "approve"})).status_code == 403
    assert (await client.post(f"/api/v1/restaurants/{boise}/food-permit/review", headers=ops, json={"decision": "reject"})).status_code == 422
    r = await client.post(f"/api/v1/restaurants/{boise}/food-permit/review", headers=ops,
                          json={"decision": "reject", "note": "The photo is blurred"})
    assert r.json()["status"] == "rejected" and r.json()["note"] == "The photo is blurred"
    a = (await client.get(f"/api/v1/restaurants/{boise}/application", headers=owner)).json()
    assert a["food_permit"]["note"] == "The photo is blurred" and not next(s for s in a["steps"] if s["key"] == "fssai")["done"]
    await client.put(f"/api/v1/restaurants/{boise}/food-permit", headers=owner, json={"number": "CDH-12345", "expires_on": until})
    r = await client.post(f"/api/v1/restaurants/{boise}/food-permit/review", headers=ops, json={"decision": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text
    r = await client.post(f"/api/v1/restaurants/{boise}/approve", headers=ops)
    assert r.status_code == 200 and r.json()["status"] == "active", r.text
    audit = await _sql("SELECT action FROM audit_log WHERE entity_id = :r AND action LIKE 'food_permit.%' ORDER BY at", r=boise)
    assert [a for (a,) in audit][-2:] == ["food_permit.rejected", "food_permit.approved"]


async def test_reminder_30_days_before_and_pause_after_expiry(client: AsyncClient, boise: str) -> None:  # noqa: F811
    from core_api.modules.catalog.service import permits
    from core_api.modules.catalog.service.menu import availability
    from shared.db import AsyncSessionLocal

    today = datetime.now(UTC).date()
    await _sql("UPDATE restaurants SET food_permit_number = 'CDH-1', food_permit_expires_on = :d, food_permit_status = 'approved', "
               "food_permit_reminded_for = NULL, paused_reason = NULL WHERE id = CAST(:r AS uuid)", d=today + timedelta(days=30), r=boise)
    async with AsyncSessionLocal() as db:
        first = [str(x) for x in await permits.remind_expiring(db, today)]
        again = [str(x) for x in await permits.remind_expiring(db, today)]
        await db.commit()
    assert boise in first and boise not in again  # once per permit
    (n,), = await _sql("SELECT count(*) FROM outbox_events WHERE event_type = 'restaurant.permit_expiring' "
                       "AND envelope->'payload'->>'restaurant_id' = :r", r=boise)
    assert n >= 1
    # A day after it expires: the hourly check pauses it; customers can't order
    await _sql("UPDATE restaurants SET food_permit_expires_on = :d WHERE id = CAST(:r AS uuid)", d=today - timedelta(days=2), r=boise)  # two days: expired in Boise whatever the UTC hour
    async with AsyncSessionLocal() as db:
        av = await availability(db, __import__("uuid").UUID(boise))
        assert not av.listed and av.paused_reason == permits.EXPIRED
        assert boise in [str(x) for x in await permits.pause_expired(db, today)]
        await db.commit()
    (reason,), = await _sql("SELECT paused_reason FROM restaurants WHERE id = CAST(:r AS uuid)", r=boise)
    assert reason == "food_permit_expired"
    # Renewed and approved: listed again
    owner, ops = await login(client, "partner.boi@example.com"), await login(client, "ops.boi@example.com", PW)
    key = (await upload(client, owner, "partner_document")).json()["key"]
    await client.put(f"/api/v1/restaurants/{boise}/food-permit", headers=owner, json={
        "number": "CDH-2", "expires_on": (today + timedelta(days=365)).isoformat(), "document_key": key})
    r = await client.post(f"/api/v1/restaurants/{boise}/food-permit/review", headers=ops, json={"decision": "approve"})
    assert r.json()["status"] == "approved" and not r.json()["paused"]
