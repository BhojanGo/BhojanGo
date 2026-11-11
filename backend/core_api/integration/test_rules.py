"""P7 rules workflow on a migrated, seeded database. Each test works in its own
new city so seeded Hyderabad/Boise rules stay as they are."""
import os
import random
import string
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

PW = "BhojanGoAdmin1"
_tokens: dict[str, dict] = {}


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def city(client: AsyncClient) -> str:
    """A new draft city in Telangana for this test."""
    h = await auth(client, "cm.in@example.com")
    code = "IN-TG-" + "".join(random.choices(string.ascii_uppercase, k=3))
    r = await client.post("/api/v1/markets/regions/IN-TG/cities", headers=h,
                          json={"code": code, "name": f"Rulepur {code[-3:]}", "center_lat": 17.3, "center_lng": 78.5})
    assert r.status_code == 201, r.text
    return code


def ctx(city: str) -> dict:
    return {"country": "IN", "region": "IN-TG", "city": city}


async def resolved(client: AsyncClient, h: dict, params: dict) -> dict:
    r = await client.get("/api/v1/rules/resolve", headers=h, params=params)
    assert r.status_code == 200, r.text
    return {x["slot"]: x for x in r.json()}


async def test_every_seeded_rule_is_valid_and_hyderabad_resolves(client: AsyncClient) -> None:
    from sqlalchemy import select

    from core_api.modules.rules.models import Rule
    from core_api.modules.rules.service import templates
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = list((await db.execute(select(Rule).where(Rule.status == "published"))).scalars())
    assert len(rows) >= 31
    for r in rows:
        templates.validate_params(r.family, r.template, r.params)

    h = await auth(client, "cm.in@example.com")
    restaurant = next(r for r in rows if r.scope_level == "restaurant").scope_id
    got = await resolved(client, h, {**ctx("IN-TG-HYD"), "restaurant_id": restaurant})
    assert got["delivery_fee"]["template"] == "distance_slabs" and got["delivery_fee"]["scope_level"] == "city"
    assert got["customer_fee:packaging_levy"]["params"]["amount"] == "10"
    assert got["customer_fee:service_fee"]["params"]["percent"] == "2"
    assert got["tax:rate_on_lines:gst_food"]["params"]["rate_percent"] == "5"
    assert got["tax:rate_on_lines:gst_fees"]["params"]["rate_percent"] == "18"
    assert got["commission:percent_by_tier"]["scope_level"] == "country"
    assert got["business:accept_timeout"]["scope_level"] == "platform"
    assert "promotion:percent_off:hyd_launch" in got


async def test_money_rule_needs_a_second_admin(client: AsyncClient, city: str) -> None:
    maker = await auth(client, "cm.in@example.com")
    checker = await auth(client, "finance.in@example.com")
    r = await client.post("/api/v1/rules", headers=maker, json={
        "family": "customer_fee", "template": "service_fee", "params": {"percent": 3, "min": 5, "max": 20},
        "scope_level": "city", "scope_id": city,
    })
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["status"] == "draft" and rule["money"] is True

    assert "customer_fee:service_fee" not in await resolved(client, maker, ctx(city))  # drafts don't apply
    r = await client.post(f"/api/v1/rules/{rule['id']}/submit", headers=maker)
    assert r.json()["status"] == "pending_approval"
    queue = (await client.get("/api/v1/rules/approvals", headers=checker)).json()
    assert rule["id"] in [q["id"] for q in queue]
    assert rule["id"] not in [q["id"] for q in (await client.get("/api/v1/rules/approvals", headers=maker)).json()]

    r = await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=maker, json={})
    assert r.status_code == 409 and "second admin" in r.text
    r = await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=checker, json={"note": "Matches the plan"})
    assert r.status_code == 200 and r.json()["status"] == "published"

    got = await resolved(client, maker, ctx(city))
    assert got["customer_fee:service_fee"]["params"]["percent"] == "3"

    hist = (await client.get(f"/api/v1/rules/{rule['id']}/history", headers=maker)).json()
    assert [a["action"] for a in hist["audit"]] == ["rule.created", "rule.submitted", "rule.approved"]
    assert hist["approvals"][rule["id"]][0]["decision"] == "approved"


async def test_business_rule_publishes_without_review(client: AsyncClient, city: str) -> None:
    h = await auth(client, "cm.in@example.com")
    r = await client.post("/api/v1/rules", headers=h, json={
        "family": "business", "template": "tip_presets", "params": {"amounts": [15, 25, 40]},
        "scope_level": "city", "scope_id": city,
    })
    r = await client.post(f"/api/v1/rules/{r.json()['id']}/submit", headers=h)
    assert r.json()["status"] == "published"
    got = await resolved(client, h, ctx(city))
    assert got["business:tip_presets"]["params"]["amounts"] == ["15", "25", "40"]
    # The country's presets still apply in Hyderabad.
    assert (await resolved(client, h, ctx("IN-TG-HYD")))["business:tip_presets"]["scope_level"] == "country"


async def _publish(client: AsyncClient, maker: dict, checker: dict, body: dict) -> dict:
    r = await client.post("/api/v1/rules", headers=maker, json=body)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    await client.post(f"/api/v1/rules/{rid}/submit", headers=maker)
    r = await client.post(f"/api/v1/rules/{rid}/approve", headers=checker, json={})
    assert r.status_code == 200, r.text
    return r.json()


async def test_versions_reject_rollback(client: AsyncClient, city: str) -> None:
    maker = await auth(client, "cm.in@example.com")
    checker = await auth(client, "finance.in@example.com")
    v1 = await _publish(client, maker, checker, {
        "family": "delivery_fee", "template": "flat", "params": {"amount": 30}, "scope_level": "city", "scope_id": city})

    # A published rule is never edited in place.
    r = await client.patch(f"/api/v1/rules/{v1['id']}", headers=maker, json={"params": {"amount": 40}})
    assert r.status_code == 409

    r = await client.post(f"/api/v1/rules/{v1['id']}/versions", headers=maker, json={"params": {"amount": 45}})
    v2 = r.json()
    assert v2["version"] == 2 and v2["status"] == "draft"
    r = await client.post(f"/api/v1/rules/{v1['id']}/versions", headers=maker, json={})
    assert r.status_code == 409  # one open draft at a time

    await client.post(f"/api/v1/rules/{v2['id']}/submit", headers=maker)
    r = await client.post(f"/api/v1/rules/{v2['id']}/reject", headers=checker, json={"note": "Too steep for launch"})
    assert r.json()["status"] == "rejected"
    assert (await resolved(client, maker, ctx(city)))["delivery_fee"]["params"]["amount"] == "30"

    await client.patch(f"/api/v1/rules/{v2['id']}", headers=maker, json={"params": {"amount": 35}})
    await client.post(f"/api/v1/rules/{v2['id']}/submit", headers=maker)
    await client.post(f"/api/v1/rules/{v2['id']}/approve", headers=checker, json={})
    assert (await resolved(client, maker, ctx(city)))["delivery_fee"]["version"] == 2

    # One click back to v1: a new version 3 with v1's settings, approved by the checker.
    r = await client.post(f"/api/v1/rules/{v1['id']}/rollback", headers=maker)
    v3 = r.json()
    assert v3["version"] == 3 and v3["status"] == "pending_approval" and v3["params"]["amount"] == "30"
    await client.post(f"/api/v1/rules/{v3['id']}/approve", headers=checker, json={})
    got = (await resolved(client, maker, ctx(city)))["delivery_fee"]
    assert (got["version"], got["params"]["amount"]) == (3, "30")

    hist = (await client.get(f"/api/v1/rules/{v1['id']}/history", headers=maker)).json()
    ends = {v["version"]: v["effective_to"] for v in hist["versions"]}
    assert ends[1] and ends[2] and ends[3] is None
    assert "rule.rolled_back" in [a["action"] for a in hist["audit"]]


async def test_future_version_and_simulator_overlay(client: AsyncClient, city: str) -> None:
    maker = await auth(client, "cm.in@example.com")
    checker = await auth(client, "finance.in@example.com")
    v1 = await _publish(client, maker, checker, {
        "family": "customer_fee", "template": "packaging_levy", "params": {"amount": 10}, "scope_level": "city", "scope_id": city})
    start = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    r = await client.post(f"/api/v1/rules/{v1['id']}/versions", headers=maker, json={"params": {"amount": 12}, "effective_from": start})
    v2 = r.json()

    # Before it is approved, the simulator can try it as if it were live.
    sim = await resolved(client, maker, {**ctx(city), "draft": v2["id"]})
    assert sim["customer_fee:packaging_levy"]["params"]["amount"] == "12"
    assert (await resolved(client, maker, ctx(city)))["customer_fee:packaging_levy"]["params"]["amount"] == "10"

    await client.post(f"/api/v1/rules/{v2['id']}/submit", headers=maker)
    await client.post(f"/api/v1/rules/{v2['id']}/approve", headers=checker, json={})
    assert (await resolved(client, maker, ctx(city)))["customer_fee:packaging_levy"]["params"]["amount"] == "10"
    later = (datetime.now(UTC) + timedelta(days=8)).isoformat()
    assert (await resolved(client, maker, {**ctx(city), "at": later}))["customer_fee:packaging_levy"]["params"]["amount"] == "12"


async def test_end_a_promotion(client: AsyncClient, city: str) -> None:
    maker = await auth(client, "cm.in@example.com")
    checker = await auth(client, "finance.in@example.com")
    promo = await _publish(client, maker, checker, {
        "family": "promotion", "template": "flat_off", "key": "monsoon",
        "params": {"amount": 50, "funded_by": "platform", "min_subtotal": 299}, "scope_level": "city", "scope_id": city})
    assert "promotion:flat_off:monsoon" in await resolved(client, maker, ctx(city))
    r = await client.post(f"/api/v1/rules/{promo['id']}/end", headers=checker, json={})
    assert r.status_code == 200
    assert "promotion:flat_off:monsoon" not in await resolved(client, maker, ctx(city))


@pytest.mark.parametrize(("email", "level", "scope", "status"), [
    ("ops.hyd@example.com", "city", "IN-TG-HYD", 403),       # city ops: view only
    ("cm.in@example.com", "city", "US-ID-BOI", 403),         # other country
    ("cm.in@example.com", "platform", "*", 403),             # platform rules: super admin
    ("viewer@example.com", "city", "IN-TG-HYD", 403),
    ("admin@example.com", "platform", "*", 201),
])
async def test_who_can_create(client: AsyncClient, email, level, scope, status) -> None:
    h = await auth(client, email)
    r = await client.post("/api/v1/rules", headers=h, json={
        "family": "business", "template": "cancel_window", "params": {"minutes": 3}, "scope_level": level, "scope_id": scope})
    assert r.status_code == status, r.text
    if status == 201:
        assert (await client.delete(f"/api/v1/rules/{r.json()['id']}", headers=h)).status_code == 204


async def test_invalid_rules_are_refused(client: AsyncClient, city: str) -> None:
    h = await auth(client, "cm.in@example.com")
    bad = [
        ({"family": "customer_fee", "template": "service_fee", "params": {"percent": 2, "min": 20, "max": 5}}, 422),
        ({"family": "customer_fee", "template": "formula", "params": {}}, 422),
        ({"family": "tax", "template": "rate_on_lines", "params": {"label": "GST", "rate_percent": 5, "target_lines": ["food"]},
          "scope_level": "zone"}, 409),  # tax can't be set per zone
    ]
    for body, status in bad:
        r = await client.post("/api/v1/rules", headers=h, json={"scope_level": "city", "scope_id": city, **body})
        assert r.status_code == status, (body, r.text)


async def test_audit_log_is_for_super_admins(client: AsyncClient) -> None:
    sup = await auth(client, "admin@example.com")
    r = await client.get("/api/v1/audit", headers=sup, params={"entity_type": "rule"})
    assert r.status_code == 200 and r.json() and r.json()[0]["entity_type"] == "rule"
    assert (await client.get("/api/v1/audit", headers=await auth(client, "cm.in@example.com"))).status_code == 403
