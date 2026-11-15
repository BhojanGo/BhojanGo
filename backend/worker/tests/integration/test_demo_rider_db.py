"""The demo rider simulator on the migrated database (app/demo_sim/runner.py),
against core_api's real API in-process:

- it signs in like the apps (phone code for seed phones), as a customer and as
  a kitchen owner, and refreshes its tokens;
- its order query reads real orders, and a real (non-demo) customer's order is
  never one it may drive, even if it were in its own set;
- the kitchen steps it takes (accept, cook) go through PUT /orders/{id}/status
  and move the order as the business rules allow.

Realtime (dispatch, GPS) runs in its own service and isn't mounted here; the
rider steps are covered by the unit tests and the QA run.
"""
import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_kitchen_steps_through_the_api_and_only_demo_orders() -> None:
    from app.demo_sim import rules, runner
    from core_api.integration.test_orders_flow import login, new_order, pay
    from core_api.main import app
    from shared.db import AsyncSessionLocal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as core:
        api = runner.Api(core, core)  # realtime isn't called in this test
        async with AsyncSessionLocal() as db:
            customer = (await db.execute(runner.USER_SQL, {"email": "customer1.hyd@example.com"})).first()
            assert customer is not None and customer.phone

        # Sign in with the phone code, as the customer app does; a stale token is renewed.
        cust = api.person(customer)
        me = await cust.call("core", "GET", "/users/me")
        assert me["email"] == "customer1.hyd@example.com"
        cust.access = "not-a-token"
        assert (await cust.call("core", "GET", "/users/me"))["email"] == "customer1.hyd@example.com"

        h = await login(core, "customer1.hyd@example.com")
        order = await new_order(core, h)
        await pay(core, h, order)

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(runner.ORDERS_SQL, {"email": "customer1.hyd@example.com"})).all()
            mine = next(r for r in rows if str(r.id) == order["id"])
            owner = (await db.execute(runner.OWNER_SQL, {"id": mine.owner_id})).first()
        o = runner._order(mine)
        assert o.status == "placed" and o.pickup and o.dropoff and not o.seeded
        assert not rules.is_sim_order(o, {o.id}), "a real customer's order is never the simulator's"

        # As for its own order: the kitchen's owner signs in and accepts, then cooks.
        city = runner.City(api, "hyd", customer)  # any user row will do as the rider here
        await city.do("accept", o, customer, owner, o.created_at)
        await city.do("prepare", o, customer, owner, o.created_at)
        r = await core.get(f"/api/v1/orders/{order['id']}", headers=h)
        assert r.json()["status"] == "preparing", r.text
        assert api.person(owner).refresh, "the kitchen's session can be refreshed"
