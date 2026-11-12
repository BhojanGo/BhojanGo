"""P21 on Postgres: the admin overview and orders cut to each admin's scopes,
and reviewing a rider's documents (only in your country)."""
import os

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import PNG, login, new_order, pay, upload
from core_api.integration.test_riders import new_rider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN_PW = "BhojanGoAdmin1"


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def test_overview_is_cut_to_your_scope(client: AsyncClient) -> None:
    sa = await login(client, "admin@example.com", ADMIN_PW)
    everything = (await client.get("/api/v1/ops/overview", headers=sa)).json()
    assert {c["code"] for c in everything["countries"]} == {"IN", "US"}
    india = next(c for c in everything["countries"] if c["code"] == "IN")
    assert india["currency"] == "INR" and any(s["name"] == "Telangana" for s in india["states"])
    hyd = next(ci for s in india["states"] for ci in s["cities"] if ci["code"] == "IN-TG-HYD")
    assert hyd["totals"]["kitchens"] >= 5 and "live" in hyd["totals"]

    ops = await login(client, "ops.hyd@example.com", ADMIN_PW)
    mine = (await client.get("/api/v1/ops/overview", headers=ops)).json()["countries"]
    assert [c["code"] for c in mine] == ["IN"]
    assert [ci["code"] for s in mine[0]["states"] for ci in s["cities"]] == ["IN-TG-HYD"]
    assert any(a["kind"] == "kitchen_application" and "Kesar Kitchen" in a["detail"] for a in mine[0]["needs_action"])
    assert (await client.get("/api/v1/ops/overview", headers=ops, params={"scope": "US"})).status_code == 403
    boi = await login(client, "ops.boi@example.com", ADMIN_PW)
    assert (await client.get("/api/v1/ops/overview", headers=boi, params={"scope": "IN-TG-HYD"})).status_code == 403


async def test_live_orders_and_search(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)
    await pay(client, cust, order)
    ops = await login(client, "ops.hyd@example.com", ADMIN_PW)
    live = (await client.get("/api/v1/ops/orders", headers=ops, params={"scope": "IN-TG-HYD"})).json()
    me = next(o for o in live if o["id"] == order["id"])
    assert me["status"] == "placed" and me["customer"].endswith(".") and me["code"] == "#" + order["id"].replace("-", "")[:6].upper()
    found = (await client.get("/api/v1/ops/orders", headers=ops, params={"view": "search", "q": me["code"]})).json()
    assert [o["id"] for o in found] == [order["id"]]
    by_phone = (await client.get("/api/v1/ops/orders", headers=ops, params={"view": "search", "q": "9000000101"})).json()
    assert order["id"] in [o["id"] for o in by_phone]
    boi = await login(client, "ops.boi@example.com", ADMIN_PW)
    assert order["id"] not in [o["id"] for o in (await client.get("/api/v1/ops/orders", headers=boi)).json()]


async def test_review_a_riders_documents_in_your_country(client: AsyncClient) -> None:
    rid, h = await new_rider("US")
    key = (await upload(client, h, "rider_document")).json()["key"]
    assert (await client.post("/api/v1/riders/me/documents", headers=h, json={"kind": "licence", "file_key": key})).status_code == 200
    cm_us, cm_in = await login(client, "cm.us@example.com", ADMIN_PW), await login(client, "cm.in@example.com", ADMIN_PW)
    docs = (await client.get("/api/v1/riders/documents", headers=cm_us, params={"country": "US"})).json()
    doc = next(d for d in docs if d["rider_id"] == rid)
    assert doc["kind"] == "licence" and doc["rider_name"] == "Jordan Lee"
    assert all(d["rider_id"] != rid for d in (await client.get("/api/v1/riders/documents", headers=cm_in)).json())
    # The file, for the admins who review it.
    r = await client.get("/api/v1/uploads/view", headers=cm_us, params={"key": key})
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert (await client.get("/api/v1/uploads/view", headers=cm_in, params={"key": key})).status_code == 404
    # Rejecting needs a reason; the other country's manager can't decide.
    url = f"/api/v1/riders/documents/{doc['id']}/review"
    assert (await client.post(url, headers=cm_us, json={"decision": "reject"})).status_code == 422
    assert (await client.post(url, headers=cm_in, json={"decision": "approve"})).status_code == 403
    r = await client.post(url, headers=cm_us, json={"decision": "reject", "note": "The photo is blurred"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    steps = {s["key"]: s for s in (await client.get("/api/v1/riders/me/onboarding", headers=h)).json()["steps"]}
    assert steps["licence"]["status"] == "rejected" and steps["licence"]["detail"] == "The photo is blurred"
