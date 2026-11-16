"""B1 on Postgres: a new number signs up as a rider (onboarding checklist) or
applies with a kitchen (partner application); both reach the admin queues."""
import os
import random

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def new_number(client: AsyncClient) -> dict:
    """A brand-new phone signs in (fixed seed code for the +919000000… range)."""
    phone = f"+9190000{random.randint(10000, 99999)}"
    assert (await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": "IN"})).status_code == 200
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": "IN"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "customer", r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_rider_signs_up_and_lands_in_onboarding(client: AsyncClient) -> None:
    h = await new_number(client)
    r = await client.post("/api/v1/riders/apply", headers=h, json={"full_name": "Kiran Rao", "city_code": "IN-TG-HYD"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "driver", r.text
    rider = {"Authorization": f"Bearer {r.json()['access_token']}"}
    o = (await client.get("/api/v1/riders/me/onboarding", headers=rider)).json()
    assert o["first_name"] == "Kiran" and o["ready"] is False and o["steps"][0]["status"] == "done"
    assert (await client.post("/api/v1/riders/apply", headers=rider, json={"full_name": "Kiran Rao", "city_code": "IN-TG-HYD"})).status_code == 200
    # A number with orders, a city we're not in, and an admin's account are refused.
    cust = await login(client, "customer1.hyd@example.com")
    assert (await client.post("/api/v1/riders/apply", headers=cust, json={"full_name": "X Y", "city_code": "IN-TG-HYD"})).json()["detail"]["code"] == "HAS_ORDERS"
    assert (await client.post("/api/v1/riders/apply", headers=await new_number(client), json={"full_name": "X Y", "city_code": "IN-TG-WGL"})).status_code == 422


async def test_kitchen_applies_and_waits_for_approval(client: AsyncClient) -> None:
    h = await new_number(client)
    r = await client.post("/api/v1/restaurants/apply", headers=h, json={
        "full_name": "Lata Menon", "kitchen_name": "Lata's Kitchen", "city_code": "IN-TG-HYD", "street": "Plot 9, Road 12",
        "area": "Banjara Hills", "zip": "500034", "lat": 17.4126, "lng": 78.4400, "cuisines": ["Kerala"]})
    assert r.status_code == 201 and r.json()["user"]["role"] == "restaurant_owner", r.text
    partner = {"Authorization": f"Bearer {r.json()['access_token']}"}
    rid = r.json()["restaurant_id"]
    mine = (await client.get("/api/v1/restaurants/mine", headers=partner)).json()
    assert [(k["id"], k["status"]) for k in mine] == [(rid, "pending_approval")]
    a = (await client.get(f"/api/v1/restaurants/{rid}/application", headers=partner)).json()
    assert a["done"] == 1 and a["current"] == "fssai"
    ops = await login(client, "ops.hyd@example.com", "BhojanGoAdmin1")
    assert rid in [k["id"] for k in (await client.get("/api/v1/restaurants/admin/pending", headers=ops)).json()]


# ── R8 F7: "Add your kitchen" on the website ─────────────────────────────────

def _signup(**over: object) -> dict:
    n = random.randint(10000, 99999)
    body = {"kitchen_name": "Amma's Kitchen", "city_code": "IN-TG-HYD", "full_name": "Lakshmi Rao", "phone": f"+9190001{n}",
            "email": f"kitchen{n}@example.com", "password": "a long enough pass", "accept_terms": True, "language": "te"}
    return {**body, **over}


async def test_terms_come_from_the_live_rules_and_markets(client: AsyncClient) -> None:
    t = (await client.get("/api/v1/kitchens/terms", params={"country": "IN", "language": "hi"})).json()
    assert t["currency"] == "INR" and t["phone_code"] == "+91"
    c = t["commission"]
    assert c["base"] == "food_subtotal" and c["starting_percent"] == "15"  # the seeded country rule, default tier B
    assert {x["tier"]: x["percent"] for x in c["tiers"]} == {"A": "18", "B": "15", "C": "12"}
    assert float(c["percent_min"]) <= 12 and float(c["percent_max"]) >= 18
    assert t["payout"] == {"frequency": "weekly", "day": "mon", "hold_days": 2}
    assert [d["key"] for d in t["documents"]] == ["fssai", "gstin", "pan", "bank"]
    assert t["documents"][0]["title"] == "FSSAI लाइसेंस"  # in the visitor's language
    status = {x["code"]: x["status"] for x in t["cities"]}
    assert status["IN-TG-HYD"] == "live" and status["IN-AP-VSKP"] == "soon" and "IN-TG-WGL" not in status  # drafts hidden
    us = (await client.get("/api/v1/kitchens/terms", params={"country": "us"})).json()
    assert us["currency"] == "USD" and [d["key"] for d in us["documents"]] == ["health_permit", "ein", "bank"]
    assert (await client.get("/api/v1/kitchens/terms", params={"country": "ZZ"})).status_code == 404


async def test_a_new_kitchen_partner_signs_up_and_continues(client: AsyncClient) -> None:
    body = _signup()
    r = await client.post("/api/v1/kitchens/apply", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "restaurant_owner" and r.json()["user"]["preferred_locale"] == "te-IN"
    rid = r.json()["restaurant_id"]
    # Save and continue later: they sign in again with the email and password
    again = await client.post("/api/v1/auth/login", json={"email": body["email"].upper(), "password": body["password"]})
    assert again.status_code == 200, again.text
    h = {"Authorization": f"Bearer {again.json()['access_token']}"}
    assert [k["id"] for k in (await client.get("/api/v1/restaurants/mine", headers=h)).json()] == [rid]
    a = (await client.get(f"/api/v1/restaurants/{rid}/application", headers=h)).json()
    assert a["current"] == "business" and a["done"] == 0 and a["status"] == "pending_approval"
    assert a["commission_percent"] == "15.0"
    a = (await client.put(f"/api/v1/restaurants/{rid}/business", headers=h, json={
        "street": "Plot 4, Road 2", "area": "Madhapur", "zip": "500081", "cuisines": ["Andhra"], "lat": 17.45, "lng": 78.39})).json()
    assert a["current"] == "fssai" and a["street"] == "Plot 4, Road 2" and a["cuisines"] == ["Andhra"]
    # The same email or phone again, in any case: one answer, no hint which
    for dup in (_signup(email=body["email"].upper()), _signup(phone=body["phone"])):
        r = await client.post("/api/v1/kitchens/apply", json=dup)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "ACCOUNT_EXISTS", r.text


async def test_kitchen_signup_is_checked(client: AsyncClient) -> None:
    async def code(**over: object) -> str:
        r = await client.post("/api/v1/kitchens/apply", json=_signup(**over))
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        return d["code"] if isinstance(d, dict) else "VALIDATION"

    assert await code(password="too short") == "PASSWORD"
    assert await code(accept_terms=False) == "TERMS"
    assert await code(city_code="IN-TG-WGL") == "CITY"  # a draft city
    assert await code(phone="+12085550199") == "PHONE_COUNTRY_MISMATCH"
    # A coming-soon city takes applications (kitchens join before it opens)
    r = await client.post("/api/v1/kitchens/apply", json=_signup(city_code="IN-AP-VSKP"))
    assert r.status_code == 201, r.text


async def test_a_signed_in_customer_applies_with_just_the_name_and_city(client: AsyncClient) -> None:
    h = await new_number(client)
    r = await client.post("/api/v1/restaurants/apply", headers=h, json={
        "full_name": "Ravi Kumar", "kitchen_name": "Ravi's Tiffins", "city_code": "IN-TG-HYD"})
    assert r.status_code == 201, r.text
    partner = {"Authorization": f"Bearer {r.json()['access_token']}"}
    a = (await client.get(f"/api/v1/restaurants/{r.json()['restaurant_id']}/application", headers=partner)).json()
    assert a["current"] == "business"
