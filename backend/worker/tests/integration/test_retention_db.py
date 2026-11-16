"""R8 F10 on the migrated database: the retention run deletes order messages older
than 90 days and support tickets resolved more than 3 years ago, keeps newer ones and
open tickets, writes one audit row with the counts, and caps delivery routes in
Redis at one day. Running it again removes nothing more."""
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_retention_deletes_what_the_privacy_notices_say() -> None:
    from app.services import retention
    from core_api.integration.test_orders_flow import login, new_order
    from core_api.main import app
    from shared.db import AsyncSessionLocal
    from shared.redis import close_redis, get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        order = await new_order(client, await login(client, "customer2.hyd@example.com"))
    oid = uuid.UUID(order["id"])
    now = datetime.now(UTC)
    old_msg, new_msg = uuid.uuid4(), uuid.uuid4()
    old_ticket, recent_ticket, open_ticket = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        sender = (await db.execute(text("SELECT id FROM users WHERE email = 'customer2.hyd@example.com'"))).scalar()
        for mid, at in ((old_msg, now - timedelta(days=91)), (new_msg, now - timedelta(days=89))):
            await db.execute(text("INSERT INTO order_messages (id, order_id, sender_id, sender_role, text, created_at) "
                                  "VALUES (:id, :o, :s, 'customer', 'retention test', :at)"),
                             {"id": mid, "o": oid, "s": sender, "at": at})
        for tid, state, resolved in ((old_ticket, "resolved", now - timedelta(days=3 * 365 + 1)),
                                     (recent_ticket, "resolved", now - timedelta(days=30)),
                                     (open_ticket, "open", None)):
            await db.execute(text(
                "INSERT INTO support_tickets (id, kind, status, country, requester_id, requester_role, topic, details, "
                "created_at, resolved_at) VALUES (:id, 'callback', :st, 'IN', :s, 'customer', 'other', '{}'::jsonb, :c, :r)"),
                {"id": tid, "st": state, "s": sender, "c": now - timedelta(days=4 * 365), "r": resolved})
        await db.commit()
    r = await get_redis()
    trail = f"trail:{uuid.uuid4()}"
    await r.rpush(trail, "[17.4, 78.4, 0]")

    counts = await retention.run_once(now)
    assert counts["order_messages"] >= 1 and counts["support_tickets"] >= 1 and counts["route_trails_capped"] >= 1
    async with AsyncSessionLocal() as db:
        left = {i for (i,) in (await db.execute(text("SELECT id FROM order_messages WHERE id IN (:a, :b)"),
                                                {"a": old_msg, "b": new_msg})).all()}
        assert left == {new_msg}
        tickets = {i for (i,) in (await db.execute(text("SELECT id FROM support_tickets WHERE id IN (:a, :b, :c)"),
                                                   {"a": old_ticket, "b": recent_ticket, "c": open_ticket})).all()}
        assert tickets == {recent_ticket, open_ticket}
        audit = (await db.execute(text("SELECT after FROM audit_log WHERE action = 'retention.purged' ORDER BY at DESC LIMIT 1"))).scalar()
        assert audit["order_messages"] >= 1 and audit["messages_older_than_days"] == 90
    assert 0 < await r.ttl(trail) <= 24 * 3600

    again = await retention.run_once(now)
    assert again["route_trails_capped"] == 0
    async with AsyncSessionLocal() as db:
        assert (await db.execute(text("SELECT count(*) FROM order_messages WHERE id = :b"), {"b": new_msg})).scalar() == 1
    await r.delete(trail)
    await close_redis()
