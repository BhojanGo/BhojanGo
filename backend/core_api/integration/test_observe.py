"""P23 on Postgres: the pilot KPIs that Prometheus scrapes agree with the data,
and Alertmanager's alerts reach the admin console (scoped) and the logs."""
import os
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login, move, new_order, pay  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
PW = "BhojanGoAdmin1"


def _alert(name: str, status: str, fp: str, city: str | None = None) -> dict:
    labels = {"alertname": name, "severity": "critical", **({"city": city} if city else {})}
    return {"status": status, "labels": labels, "annotations": {"summary": f"{name} test", "description": "from the test"},
            "startsAt": datetime.now(UTC).isoformat(), "endsAt": datetime.now(UTC).isoformat() if status == "resolved" else "0001-01-01T00:00:00Z",
            "fingerprint": fp}


async def test_alerts_reach_the_console(client: AsyncClient, monkeypatch) -> None:  # noqa: F811
    from shared.config import get_settings

    url = "/api/v1/ops/alerts/webhook"
    body = {"status": "firing", "alerts": [_alert("OrdersWithoutRider", "firing", "fp-hyd-1", "IN-TG-HYD"),
                                           _alert("ErrorSpike", "firing", "fp-global-1")]}
    assert (await client.post(url, json=body)).status_code == 401  # no token configured: refused
    monkeypatch.setattr(get_settings(), "ALERT_WEBHOOK_TOKEN", "test-token")
    assert (await client.post(url, json=body, headers={"Authorization": "Bearer wrong"})).status_code == 401
    assert (await client.post(url, json=body, headers={"Authorization": "Bearer test-token"})).status_code == 204
    assert (await client.post(url, json=body, headers={"Authorization": "Bearer test-token"})).status_code == 204  # repeat: same rows

    def names(r) -> list[str]:  # type: ignore[no-untyped-def]
        return sorted(a["name"] for a in r.json() if a["summary"].endswith(" test"))

    hyd = await login(client, "ops.hyd@example.com", PW)
    assert names(await client.get("/api/v1/ops/alerts", headers=hyd)) == ["OrdersWithoutRider"]  # not the platform-wide one
    boise = await login(client, "ops.boi@example.com", PW)
    assert names(await client.get("/api/v1/ops/alerts", headers=boise)) == []
    admin = await login(client, "admin@example.com", PW)
    assert names(await client.get("/api/v1/ops/alerts", headers=admin)) == ["ErrorSpike", "OrdersWithoutRider"]

    done = {"status": "resolved", "alerts": [_alert("OrdersWithoutRider", "resolved", "fp-hyd-1", "IN-TG-HYD"),
                                             _alert("ErrorSpike", "resolved", "fp-global-1")]}
    assert (await client.post(url, json=done, headers={"Authorization": "Bearer test-token"})).status_code == 204
    assert names(await client.get("/api/v1/ops/alerts", headers=admin)) == []
    resolved = (await client.get("/api/v1/ops/alerts", headers=admin, params={"state": "resolved"})).json()
    assert any(a["name"] == "ErrorSpike" and a["ends_at"] for a in resolved)


async def test_kpis_for_prometheus(client: AsyncClient) -> None:  # noqa: F811
    from prometheus_client import REGISTRY
    from sqlalchemy import text

    from core_api.modules.orders.service import kpi
    from shared.db import AsyncSessionLocal

    cust = await login(client, "customer3.hyd@example.com")
    # A ready order with no rider for six minutes, and a payment that failed just now.
    order = await new_order(client, cust)
    await pay(client, cust, order)
    partner = await login(client, "partner.hyd@example.com")
    for s in ("accepted", "preparing", "ready"):
        assert (await move(client, partner, order["id"], s)).status_code == 200
    failing = await new_order(client, cust)
    await pay(client, cust, failing, outcome="failed")
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE orders SET actual_ready_at = :t WHERE id = :i"),
                         {"t": datetime.now(UTC) - timedelta(minutes=6), "i": order["id"]})
        await db.commit()
        assert await kpi.refresh(db) >= 2

    def g(name: str) -> float:
        return REGISTRY.get_sample_value(name, {"country": "IN", "city": "IN-TG-HYD"}) or 0.0

    assert g("bhojango_orders_waiting_for_rider_5m") >= 1
    assert g("bhojango_payment_failures_15m") >= 1
    assert g("bhojango_orders_live") >= 1 and g("bhojango_orders_today") >= 1
    assert REGISTRY.get_sample_value("bhojango_kpi_refreshed_timestamp_seconds") > 0
    from sqlalchemy import update

    from core_api.modules.orders.models.order import Order

    async with AsyncSessionLocal() as db:  # don't leave a ready order for other tests' riders
        await db.execute(update(Order).where(Order.id == order["id"]).values(status="cancelled"))
        await db.commit()
