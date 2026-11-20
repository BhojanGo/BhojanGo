"""R20: the whole app store review order on the migrated database, as in production at
go-live: the review accounts command makes the hidden review city; the review customer
signs in with their password, prices and places an order there (total $0.00, no payment
provider called); the review simulator (app/demo_sim/review.py, REVIEW_SIM) then plays
the review kitchen and delivery partner through core_api's signed step endpoint
(core_api in-process) until the order is delivered.

And it never moves anything else: a normal customer's order (normal city, paid) and the
review customer's own order outside the review city are never read nor moved.
"""
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def core():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        await close_redis()
        await engine.dispose()


async def test_the_review_simulator_delivers_the_review_order_and_nothing_else(core: AsyncClient, monkeypatch) -> None:
    from app.demo_sim import review as R
    from core_api.integration.test_orders_flow import login, new_order, pay
    from core_api.integration.test_review_accounts import bearer, remove
    from core_api.integration.test_review_orders import CODE, make_review_city, no_providers, quote_and_order, review_kitchen

    cmd, logins, emails = await make_review_city()
    try:
        calls = no_providers(monkeypatch)
        # The reviewer: signs in with the password the command printed, orders as the app does.
        h = await bearer(core, logins["BhojanGo"].email, logins["BhojanGo"].password)
        kitchen = await review_kitchen(core, cmd, h)
        quote, order = await quote_and_order(core, cmd, h, kitchen["id"])
        assert Decimal(quote["total"]) == 0 and order["status"] == "placed" and calls == []
        monkeypatch.undo()  # the normal orders below pay through the (fake) gateway

        # Orders that aren't review orders, open and waiting for their kitchen.
        normal_h = await login(core, "customer1.hyd@example.com")
        normal = await new_order(core, normal_h)
        await pay(core, normal_h, normal)
        outside = await new_order(core, h)  # the review customer, outside the review city
        await pay(core, h, outside)
        for o, who in ((normal, normal_h), (outside, h)):
            assert (await core.get(f"/api/v1/orders/{o['id']}", headers=who)).json()["status"] == "placed"

        # The simulator reads only the review order.
        assert [o.id for o in await R.review_orders()] == [order["id"]]

        # Tick by tick (the clock far enough on that nothing waits) until it is delivered.
        steps = []
        for _ in range(10):
            steps += [s for _, s in await R.tick(core, datetime.now(UTC) + timedelta(hours=1))]
            if (await core.get(f"/api/v1/orders/{order['id']}", headers=h)).json()["status"] == "delivered":
                break
        assert steps == ["accept", "prepare", "assign", "ready", "pick_up", "deliver"], steps
        mine = (await core.get(f"/api/v1/orders/{order['id']}", headers=h)).json()
        assert mine["status"] == "delivered" and mine["driver_id"]
        rider = await bearer(core, logins["BhojanGo Delivery"].email, logins["BhojanGo Delivery"].password)
        assert str(mine["driver_id"]) == (await core.get("/api/v1/users/me", headers=rider)).json()["id"]
        assert await R.review_orders() == []  # nothing left to do
        assert await R.tick(core, datetime.now(UTC) + timedelta(hours=2)) == []

        # The other orders are exactly as they were.
        for o, who in ((normal, normal_h), (outside, h)):
            got = (await core.get(f"/api/v1/orders/{o['id']}", headers=who)).json()
            assert got["status"] == "placed" and got["driver_id"] is None, got
        # Even asked directly, the step endpoint refuses them (the second check, in core_api).
        for o in (normal, outside):
            with pytest.raises(RuntimeError, match="404"):
                await R.send(core, o["id"], "accept")
    finally:
        await remove(CODE, emails)
