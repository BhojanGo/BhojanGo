"""R28 on Postgres: an order still without a delivery partner after the city's minutes (realtime's
business:no_partner_alert) is an alert for admin Operations in its city, and its estimate moves to the
later time the customer is told; a partner accepting resolves it. The dispatch info carries the city's
offer rules (timeout, exclusion, alert minutes)."""
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login, move, new_order, pay  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def signed(client: AsyncClient, method: str, path: str, body: dict | None = None):  # type: ignore[no-untyped-def]  # noqa: F811
    from shared import internal_auth

    data = json.dumps(body).encode() if body is not None else b""
    return await client.request(method, path, content=data or None,
                                headers={"content-type": "application/json", **internal_auth.sign(method, path, data)})


async def test_no_partner_alert_fires_moves_the_estimate_and_resolves(client: AsyncClient) -> None:  # noqa: F811
    from core_api.modules.orders.models.order import Order
    from core_api.modules.support.models import OpsAlert
    from shared.db import AsyncSessionLocal

    cust, partner = await login(client, "customer3.hyd@example.com"), await login(client, "partner.hyd@example.com")
    order = await new_order(client, cust)
    await pay(client, cust, order)
    for s in ("accepted", "preparing", "almost_ready", "ready"):
        assert (await move(client, partner, order["id"], s)).status_code == 200

    info = (await signed(client, "GET", f"/api/v1/internal/orders/{order['id']}/dispatch")).json()
    assert (info["offer_timeout_seconds"], info["offer_exclusion_seconds"], info["no_partner_alert_minutes"]) == (30, 120, 8)

    later = (datetime.now(UTC) + timedelta(minutes=55)).replace(microsecond=0)
    path = f"/api/v1/internal/orders/{order['id']}/no-partner"
    assert (await client.post(path, json={"firing": True})).status_code in (401, 403)  # signed only
    r = await signed(client, "POST", path, {"firing": True, "waited_minutes": 8, "eta": later.isoformat()})
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as db:
        alert = (await db.execute(OpsAlert.__table__.select().where(OpsAlert.fingerprint == f"no-partner-{order['id']}"))).one()
        o = await db.get(Order, uuid.UUID(order["id"]))
        assert alert.status == "firing" and alert.city == o.market_city and "no delivery partner after 8 min" in alert.summary
        assert o.estimated_delivery_time == later

    r = await signed(client, "POST", path, {"firing": False})
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as db:
        alert = (await db.execute(OpsAlert.__table__.select().where(OpsAlert.fingerprint == f"no-partner-{order['id']}"))).one()
        assert alert.status == "resolved" and alert.ends_at is not None
