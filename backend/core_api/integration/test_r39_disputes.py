"""R39 item 4 on Postgres: chargebacks through the fake provider's webhook, shaped as Stripe's
charge.dispute.* events (the Stripe test-mode cards run in tools/stripe_e2e). An open dispute holds the
restaurant's share from its next payout run; won releases it; lost charges the restaurant for food-quality
reasons and BhojanGo for fraud. Ops get an alert; admin Finance lists it and takes evidence."""
import json
import os
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import PNG, login
from core_api.integration.test_payments_refunds import delivered_order
from core_api.integration.test_payouts import deliver_last_week, ist_last_week

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean():
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        for t in ("payment_disputes", "payout_statements", "payout_runs", "payout_accounts"):
            await db.execute(text(f"DELETE FROM {t}"))
        await db.commit()
    yield


async def _sql(q: str, **p):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(text(q), p)
        rows = res.all() if res.returns_rows else []
        await db.commit()
        return rows


async def dispute_event(client: AsyncClient, kind: str, dispute: dict) -> dict:
    from core_api.modules.payments.service.gateways import FAKE_SIGNATURE_HEADER, sign_fake

    body = json.dumps({"id": f"evt_fake_{uuid.uuid4().hex[:16]}", "type": f"dispute.{kind}", "dispute": dispute}).encode()
    r = await client.post("/api/v1/payments/fake/webhook", content=body, headers={FAKE_SIGNATURE_HEADER: sign_fake(body)})
    assert r.status_code == 200, r.text
    return r.json()


async def paid_order(client: AsyncClient) -> tuple[dict, str, int]:
    cust = await login(client, "customer1.hyd@example.com")
    order = await delivered_order(client, cust)
    (pi, amount), = await _sql("SELECT provider_payment_id, amount FROM payment_intents WHERE order_id = CAST(:o AS uuid) "
                               "AND status = 'succeeded'", o=order["id"])
    return order, pi, amount


async def run_week(client: AsyncClient, finance: dict) -> dict:
    start, end = ist_last_week()
    r = await client.post("/api/v1/finance/payout-runs", headers=finance,
                          json={"country": "IN", "period_start": start.isoformat(), "period_end": end.isoformat()})
    assert r.status_code == 201, r.text
    detail = (await client.get(f"/api/v1/finance/payout-runs/{r.json()['id']}", headers=finance)).json()
    return next(s for s in detail["statements"] if s["payee_type"] == "restaurant" and s["payee_name"] == "Spice Route Kitchen")


async def test_open_dispute_holds_the_share_alerts_ops_and_a_win_releases_it(client: AsyncClient, monkeypatch) -> None:
    from core_api.integration.mock_webhook import MockWebhook
    from shared.config import get_settings

    order, pi, amount = await paid_order(client)
    (payout, card_fee), = await _sql("SELECT restaurant_payout, card_fee FROM orders WHERE id = CAST(:o AS uuid)",
                                           o=order["id"])
    share = int((Decimal(payout) - Decimal(card_fee)) * 100)
    with MockWebhook() as hook:
        monkeypatch.setattr(get_settings(), "PAGING_WEBHOOK_URL", hook.url)
        dp = f"dp_test_{uuid.uuid4().hex[:12]}"
        out = await dispute_event(client, "created", {"id": dp, "amount": amount, "currency": "inr", "reason": "fraudulent",
                                                      "status": "needs_response", "payment_intent": pi, "due_by": 1893456000})
        again = await dispute_event(client, "created", {"id": dp, "amount": amount, "currency": "inr", "reason": "fraudulent",
                                                        "status": "needs_response", "payment_intent": pi})
        assert out["outcome"] is None and again["dispute"] == out["dispute"]  # one dispute, however often it is sent
        # ops are alerted: the Operations page and one page through the webhook
        assert len(hook.received) == 1 and "Chargeback opened" in hook.received[0]["text"], hook.received
    ops = await login(client, "ops.hyd@example.com", ADMIN)
    alerts = (await client.get("/api/v1/ops/alerts", headers=ops, params={"scope": "IN-TG-HYD"})).json()
    assert any(a["name"] == "ChargebackOpened" for a in alerts), alerts

    finance = await login(client, "finance.in@example.com", ADMIN)
    listed = (await client.get("/api/v1/finance/disputes", headers=finance, params={"country": "IN", "state": "open"})).json()
    d = next(x for x in listed if x["provider_dispute_id"] == dp)
    assert d["order_id"] == order["id"] and d["restaurant"] == "Spice Route Kitchen" and d["held"] == min(share, amount)
    assert d["next_payout"] == -d["held"] and d["evidence_due_by"].startswith("2030-01-01")
    # Evidence: a file and a note, viewable by finance; nothing for a customer
    r = await client.post(f"/api/v1/finance/disputes/{d['id']}/evidence", headers=finance, data={"note": "Delivered to the door, photo attached"},
                          files={"file": ("door.png", PNG, "image/png")})
    assert r.status_code == 201, r.text
    assert (await client.get(f"/api/v1/finance/disputes/{d['id']}/evidence/1", headers=finance)).content == PNG
    cust = await login(client, "customer1.hyd@example.com")
    assert (await client.get("/api/v1/finance/disputes", headers=cust, params={"country": "IN"})).status_code == 403

    # The payout run holds the share
    await deliver_last_week(order["id"])
    stmt = await run_week(client, finance)
    assert Decimal(stmt["summary"]["disputes"]) == -Decimal(d["held"]) / 100
    assert [(x["kind"], x["amount"]) for x in stmt["summary"]["dispute_lines"]] == [("dispute_hold", -d["held"])]

    # Won: the next run gives it back
    await dispute_event(client, "closed", {"id": dp, "status": "won"})
    after = (await client.get(f"/api/v1/finance/disputes/{d['id']}", headers=finance)).json()
    assert after["outcome"] == "won" and after["restaurant_loss"] == 0 and after["next_payout"] == d["held"]
    await _sql("DELETE FROM payout_statements")  # the same week again: the hold was applied by the first run
    await _sql("DELETE FROM payout_runs")
    stmt = await run_week(client, finance)
    assert [(x["kind"], x["amount"]) for x in stmt["summary"]["dispute_lines"]] == [("dispute_released", d["held"])]
    assert (await client.get(f"/api/v1/finance/disputes/{d['id']}", headers=finance)).json()["next_payout"] == 0


@pytest.mark.parametrize("reason,bearer", [("product_unacceptable", "restaurant"), ("fraudulent", "platform")])
async def test_a_lost_dispute_is_borne_per_the_agreement(client: AsyncClient, reason: str, bearer: str) -> None:
    order, pi, amount = await paid_order(client)
    (food,), = await _sql("SELECT subtotal FROM orders WHERE id = CAST(:o AS uuid)", o=order["id"])
    food_minor = int(Decimal(food) * 100)
    dp = f"dp_test_{uuid.uuid4().hex[:12]}"
    await dispute_event(client, "created", {"id": dp, "amount": amount, "currency": "inr", "reason": reason,
                                            "status": "needs_response", "payment_intent": pi})
    finance = await login(client, "finance.in@example.com", ADMIN)
    d = next(x for x in (await client.get("/api/v1/finance/disputes", headers=finance, params={"country": "IN"})).json()
             if x["provider_dispute_id"] == dp)
    # Evidence through admin; the fake provider decides like Stripe test mode ("losing_evidence" loses)
    assert (await client.post(f"/api/v1/finance/disputes/{d['id']}/submit", headers=finance)).status_code == 422  # nothing yet
    await client.post(f"/api/v1/finance/disputes/{d['id']}/evidence", headers=finance, data={"note": "losing_evidence"})
    r = await client.post(f"/api/v1/finance/disputes/{d['id']}/submit", headers=finance)
    assert r.status_code == 200, r.text
    lost = r.json()
    assert lost["outcome"] == "lost" and lost["loss_bearer"] == bearer and lost["evidence_submitted_at"]
    if bearer == "restaurant":  # the food amount, the rest (fees, tax, tip) is BhojanGo's
        assert lost["restaurant_loss"] == min(food_minor, amount) and lost["platform_loss"] == amount - lost["restaurant_loss"]
    else:
        assert lost["restaurant_loss"] == 0 and lost["platform_loss"] == amount
    assert (await client.post(f"/api/v1/finance/disputes/{d['id']}/submit", headers=finance)).status_code == 409  # once
    # Never held (it closed before a payout run): the next run charges only the restaurant's part
    await deliver_last_week(order["id"])
    stmt = await run_week(client, finance)
    lines = stmt["summary"].get("dispute_lines", [])
    if bearer == "restaurant":
        assert [(x["kind"], x["amount"]) for x in lines] == [("dispute_loss", -lost["restaurant_loss"])]
    else:
        assert lines == []
