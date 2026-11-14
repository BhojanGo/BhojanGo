"""Commission rules end to end (Pricing & Rules, commissions first).

Precedence restaurant > city > country is unit-tested in the engine; here, on the
migrated, seeded database: an override wins and an ended one falls back, old
orders keep the rate they were priced with, only admins with the scope can touch
a rule, tier changes and batching need a second admin, and the preview.
Everything these tests change is put back, so the rest of the suite (and its
₹638.22 worked example) sees the seeded rates."""
import os
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login, new_order, pay

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
PW = "BhojanGoAdmin1"


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def spice_route(client: AsyncClient) -> str:
    return next(r["id"] for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")


async def snapshot_commission(order_id: str) -> Decimal:
    from sqlalchemy import select

    from core_api.modules.pricing.models import OrderPricingSnapshot
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        snap = (await db.execute(select(OrderPricingSnapshot).where(OrderPricingSnapshot.order_id == uuid.UUID(order_id)))).scalar_one()
    return Decimal(snap.split["detail"]["commission"])


async def test_restaurant_override_wins_ends_and_falls_back(client: AsyncClient) -> None:
    cm, fin = await login(client, "cm.in@example.com", PW), await login(client, "finance.in@example.com", PW)
    cust = await login(client, "customer1.hyd@example.com")
    rid = await spice_route(client)
    view = f"/api/v1/rules/commission/restaurants/{rid}"
    start = (await client.get(view, headers=cm)).json()
    assert start["rate_source"]["scope_level"] == "country" and start["percent"] == "15"  # IN tier B

    before = await new_order(client, cust)  # priced at the country's 15%
    r = await client.post("/api/v1/rules", headers=cm, json={
        "family": "commission", "template": "percent", "params": {"percent": 12}, "name": "Spice Route launch deal",
        "scope_level": "restaurant", "scope_id": rid})
    assert r.status_code == 201, r.text
    rule = r.json()
    try:
        assert (await client.post(f"/api/v1/rules/{rule['id']}/submit", headers=cm)).json()["status"] == "pending_approval"
        assert (await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=cm, json={})).status_code == 409  # maker can't check
        r = await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=fin, json={"note": "agreed in the contract"})
        assert r.status_code == 200 and r.json()["status"] == "published", r.text
        now = (await client.get(view, headers=cm)).json()
        assert now["percent"] == "12" and now["rate_source"]["scope_level"] == "restaurant" and now["rate_source"]["rule_id"] == rule["id"]
        during = await new_order(client, cust)
        food = Decimal(str(during["subtotal"]))
        assert await snapshot_commission(during["id"]) == (food * 12 / 100).quantize(Decimal("0.01"))
        # End it now: the restaurant falls back to the country's tier rate.
        assert (await client.post(f"/api/v1/rules/{rule['id']}/end", headers=cm, json={})).status_code == 200
        back = (await client.get(view, headers=cm)).json()
        assert back["percent"] == "15" and back["rate_source"]["scope_level"] == "country"
        after = await new_order(client, cust)
        assert await snapshot_commission(after["id"]) == (Decimal(str(after["subtotal"])) * 15 / 100).quantize(Decimal("0.01"))
        # Orders keep the rate they were priced with, whatever happens to the rule later.
        assert await snapshot_commission(before["id"]) == (Decimal(str(before["subtotal"])) * 15 / 100).quantize(Decimal("0.01"))
        assert await snapshot_commission(during["id"]) == (food * 12 / 100).quantize(Decimal("0.01"))
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=cm, json={})
    await pay(client, cust, before)  # (leave nothing unpaid behind for the timeout tests)


async def _admin_at(role: str, scope: str) -> str:
    """A fresh admin with one role at one scope; returns their email."""
    from core_api.modules.identity.models.admin_role import AdminRoleAssignment
    from core_api.modules.identity.models.user import User
    from core_api.modules.identity.service.security import hash_password
    from shared.db import AsyncSessionLocal

    email = f"{role}.{scope.lower()}.{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as db:
        u = User(email=email, full_name="Scoped Admin", hashed_password=hash_password(PW), role="admin", country=scope[:2])
        db.add(u)
        await db.flush()
        db.add(AdminRoleAssignment(user_id=u.id, role=role, scope=scope))
        await db.commit()
    return email


@pytest.mark.parametrize(("who", "level", "scope_id", "allowed"), [
    ("boise_manager", "city", "US-ID-BOI", True),     # their own city
    ("boise_manager", "country", "US", False),        # not the country's rule
    ("boise_manager", "city", "IN-TG-HYD", False),    # not another city
    ("ops.boi@example.com", "city", "US-ID-BOI", False),  # city ops can't edit rules at all
    ("cm.us@example.com", "country", "IN", False),    # another country
    ("cm.us@example.com", "city", "US-ID-BOI", True),
])
async def test_scoped_admins_only_touch_their_own_rules(client: AsyncClient, who: str, level: str, scope_id: str, allowed: bool) -> None:
    email = await _admin_at("country_manager", "US-ID-BOI") if who == "boise_manager" else who
    h = await login(client, email, PW)
    r = await client.post("/api/v1/rules", headers=h, json={
        "family": "commission", "template": "percent", "params": {"percent": 14}, "scope_level": level, "scope_id": scope_id})
    assert r.status_code == (201 if allowed else 403), r.text
    if allowed:  # a draft: delete it
        assert (await client.delete(f"/api/v1/rules/{r.json()['id']}", headers=h)).status_code == 204


async def test_tier_change_needs_a_second_admin_and_is_audited(client: AsyncClient) -> None:
    cm, fin = await login(client, "cm.in@example.com", PW), await login(client, "finance.in@example.com", PW)
    rid = await spice_route(client)
    base = f"/api/v1/rules/commission/restaurants/{rid}"
    r = await client.post(f"{base}/tier", headers=cm, json={"tier": "A", "note": "Top seller, moved to tier A"})
    assert r.status_code == 201, r.text
    change = r.json()["id"]
    pending = (await client.get(base, headers=cm)).json()
    assert pending["tier"] == "B" and pending["pending_tier_change"]["to"] == "A"
    assert (await client.post(f"/api/v1/rules/commission/tier-changes/{change}/approve", headers=cm, json={})).status_code == 409
    r = await client.post(f"/api/v1/rules/commission/tier-changes/{change}/approve", headers=fin, json={"note": "ok"})
    assert r.status_code == 200 and r.json()["tier"] == "A", r.text
    now = (await client.get(base, headers=cm)).json()
    assert now["tier"] == "A" and now["percent"] == "18" and now["pending_tier_change"] is None
    audit = (await client.get("/api/v1/audit", headers=await login(client, "admin@example.com", PW),
                              params={"entity_type": "restaurant"})).json()
    assert any(a["action"] == "restaurant.tier_changed" and a["entity_id"] == rid for a in audit)
    # put it back (another approved change)
    back = (await client.post(f"{base}/tier", headers=cm, json={"tier": "B", "note": "Back to B after the test"})).json()["id"]
    assert (await client.post(f"/api/v1/rules/commission/tier-changes/{back}/approve", headers=fin, json={})).json()["tier"] == "B"


async def test_preview_recalculates_the_last_days(client: AsyncClient) -> None:
    cm = await login(client, "cm.in@example.com", PW)
    cust = await login(client, "customer1.hyd@example.com")
    r = await client.post("/api/v1/rules", headers=cm, json={
        "family": "commission", "template": "percent", "params": {"percent": 10}, "scope_level": "city", "scope_id": "IN-TG-HYD"})
    draft = r.json()
    try:
        p = (await client.get(f"/api/v1/rules/commission/preview/{draft['id']}", headers=cm)).json()
        assert p["days"] == 7 and p["orders"] >= 0
        assert Decimal(p["payout_difference"]) == Decimal(p["commission_now"]) - Decimal(p["commission_new"])
        if p["orders"]:  # Hyderabad orders delivered earlier in the suite: 15% now, 10% with the draft
            assert Decimal(p["commission_new"]) < Decimal(p["commission_now"]) and Decimal(p["payout_difference"]) > 0
    finally:
        assert (await client.delete(f"/api/v1/rules/{draft['id']}", headers=cm)).status_code == 204
    assert cust  # (signed in to keep the helper's rate limits warm)


async def test_batching_needs_a_second_admin(client: AsyncClient) -> None:
    cm = await login(client, "cm.in@example.com", PW)
    rules = (await client.get("/api/v1/rules", headers=cm, params={"family": "business"})).json()
    live = next(r for r in rules if r["template"] == "batching" and r["market_scope"] == "IN-TG-HYD" and r["status"] == "published")
    assert live["money"] is True  # the console shows it needs approval
    v = (await client.post(f"/api/v1/rules/{live['id']}/versions", headers=cm, json={"params": {"live": True}})).json()
    try:
        assert (await client.post(f"/api/v1/rules/{v['id']}/submit", headers=cm)).json()["status"] == "pending_approval"
    finally:
        await client.delete(f"/api/v1/rules/{v['id']}", headers=cm)  # rejected/draft only; a pending one is sent back first
        fin = await login(client, "finance.in@example.com", PW)
        await client.post(f"/api/v1/rules/{v['id']}/reject", headers=fin, json={"note": "test only"})
        await client.delete(f"/api/v1/rules/{v['id']}", headers=cm)
