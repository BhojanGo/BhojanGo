"""Item 2: batch rider pay on Postgres. When a rider takes two orders as one batch, the
first drop-off pays as usual; the second pays no base, but distance + waiting + the
city's batch bonus (Hyderabad ₹10), and the rider's statement shows it."""
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login, move, new_order, pay, user_id  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def assign_in_batch(client: AsyncClient, order_id: str, rider: dict, batch_id: str, position: int):  # type: ignore[no-untyped-def]
    import json

    from shared import internal_auth

    path = f"/api/v1/internal/orders/{order_id}/assign-rider"
    body = json.dumps({"rider_id": user_id(rider), "batch_id": batch_id, "batch_position": position}).encode()
    return await client.post(path, content=body, headers={"content-type": "application/json",
                                                          **internal_auth.sign("POST", path, body)})


async def ready_order(client: AsyncClient, cust: dict, partner: dict) -> dict:
    order = await new_order(client, cust)
    await pay(client, cust, order)
    for s in ("accepted", "preparing", "almost_ready", "ready"):
        assert (await move(client, partner, order["id"], s)).status_code == 200
    return order


async def test_second_drop_off_pays_the_batch_rate(client: AsyncClient) -> None:
    from core_api.modules.finance.service import statements as S
    from core_api.modules.finance.service.payouts import _orders_for_period
    from core_api.modules.orders.models.order import Order
    from shared.db import AsyncSessionLocal

    cust, partner = await login(client, "customer3.hyd@example.com"), await login(client, "partner.hyd@example.com")
    rider = await login(client, "rider3.hyd@example.com")
    first, second = await ready_order(client, cust, partner), await ready_order(client, cust, partner)
    batch = str(uuid.uuid4())

    r1 = await assign_in_batch(client, first["id"], rider, batch, 1)
    r2 = await assign_in_batch(client, second["id"], rider, batch, 2)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    # the offer card's batch rate: the order's rider pay without the base (₹25 in India), + ₹10
    info = r2.json()
    assert Decimal(info["rider_pay_batched"]) == Decimal(info["rider_pay"]) - Decimal("25") + Decimal("10")
    # a bad place in a batch is refused
    assert (await assign_in_batch(client, second["id"], rider, batch, 9)).status_code == 422

    async with AsyncSessionLocal() as db:
        o1, o2 = await db.get(Order, uuid.UUID(first["id"])), await db.get(Order, uuid.UUID(second["id"]))
        assert (o1.batch_position, o1.batch_bonus) == (1, None)
        assert (o2.batch_position, o2.batch_bonus, o2.batch_id) == (2, Decimal("10.00"), o1.batch_id)

    for o in (first, second):
        assert (await move(client, rider, o["id"], "picked_up")).status_code == 200
        assert (await move(client, rider, o["id"], "delivered")).json()["status"] == "delivered"

    today = datetime.now(UTC).date()
    async with AsyncSessionLocal() as db:
        orders = await _orders_for_period(db, "IN", today - timedelta(days=1), today + timedelta(days=1),
                                          rider_id=uuid.UUID(user_id(rider)))
    _, _, lines = S.rider_statement(orders, floor_per_hour=None)
    by_id = {ln["order_id"]: ln for ln in lines}
    assert by_id[first["id"]]["base"] == "25.00" and "batch_bonus" not in by_id[first["id"]]
    assert by_id[second["id"]]["base"] == "0.00" and by_id[second["id"]]["batch_bonus"] == "10.00"
