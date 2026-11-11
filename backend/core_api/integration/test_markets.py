"""P6 markets against a migrated, seeded PostGIS database (see test_migrated_db.py).

    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration -v
"""
import os
import random
import string

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

ADMIN_PW = "BhojanGoAdmin1"
MADHAPUR = (17.4483, 78.3915)
KOKAPET_DRAFT = (17.400, 78.330)
BOISE_DOWNTOWN = (43.615, -116.2023)
ARABIAN_SEA = (15.0, 65.0)


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def auth(client: AsyncClient, email: str, password: str = ADMIN_PW) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def rand(n: int = 3) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=n))


def box(lat: float, lng: float, d: float = 0.01) -> dict:
    ring = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]]
    return {"type": "Polygon", "coordinates": [ring]}


# ── locate ────────────────────────────────────────────────────────────────────

async def test_locate(client: AsyncClient) -> None:
    r = (await client.get("/api/v1/markets/locate", params={"lat": MADHAPUR[0], "lng": MADHAPUR[1]})).json()
    assert r["serviceable"] and r["zone_name"] == "Madhapur" and r["city_code"] == "IN-TG-HYD"
    assert r["currency"] == "INR" and r["min_order"] == "99.00" and r["status"] == "live"

    r = (await client.get("/api/v1/markets/locate", params={"lat": BOISE_DOWNTOWN[0], "lng": BOISE_DOWNTOWN[1]})).json()
    assert r["serviceable"] and r["city_code"] == "US-ID-BOI" and r["status"] == "beta"

    r = (await client.get("/api/v1/markets/locate", params={"lat": KOKAPET_DRAFT[0], "lng": KOKAPET_DRAFT[1]})).json()
    assert not r["serviceable"] and "Hyderabad" in r["reason"]

    r = (await client.get("/api/v1/markets/locate", params={"lat": ARABIAN_SEA[0], "lng": ARABIAN_SEA[1]})).json()
    assert r == {**r, "serviceable": False, "reason": "We don't deliver here yet"}


# ── overview and scopes ───────────────────────────────────────────────────────

async def test_overview_is_scoped(client: AsyncClient) -> None:
    r = await client.get("/api/v1/markets", headers=await auth(client, "admin@example.com"))
    assert {c["code"] for c in r.json()} >= {"IN", "US"}
    india = next(c for c in r.json() if c["code"] == "IN")
    tg = next(rg for rg in india["regions"] if rg["code"] == "IN-TG")
    hyd = next(c for c in tg["cities"] if c["code"] == "IN-TG-HYD")
    assert hyd["zone_count"] >= 8 and hyd["live_zone_count"] >= 7
    assert all(hyd["launch_checklist"].values())
    wgl = next(c for c in tg["cities"] if c["code"] == "IN-TG-WGL")
    assert wgl["launch_checklist"]["zones_drawn"] is False

    ops = (await client.get("/api/v1/markets", headers=await auth(client, "ops.hyd@example.com"))).json()
    assert [c["code"] for c in ops] == ["IN"]
    assert [rg["code"] for rg in ops[0]["regions"]] == ["IN-TG"]
    assert [c["code"] for c in ops[0]["regions"][0]["cities"]] == ["IN-TG-HYD"]

    boi = (await client.get("/api/v1/markets", headers=await auth(client, "ops.boi@example.com"))).json()
    assert [c["code"] for c in boi] == ["US"]

    customer = await auth(client, "customer1.hyd@example.com", "BhojanGo123")
    assert (await client.get("/api/v1/markets", headers=customer)).status_code == 403


async def test_city_detail_and_inherited_settings(client: AsyncClient) -> None:
    h = await auth(client, "cm.in@example.com")
    d = (await client.get("/api/v1/markets/cities/IN-TG-HYD", headers=h)).json()
    assert d["name"] == "Hyderabad" and d["country"]["code"] == "IN" and d["region"]["name"] == "Telangana"
    zone = next(z for z in d["zones"] if z["name"] == "Hitech City")
    assert zone["polygon"]["type"] == "Polygon" and 3 < zone["area_km2"] < 6
    settings = {s["key"]: s for s in d["effective_settings"]}
    assert settings["currency"]["value"] == "INR" and settings["currency"]["source"] == "India"
    assert settings["service_hours"]["source"] == "Hyderabad"

    # Override at the city, then reset to inherited.
    r = await client.patch("/api/v1/markets/cities/IN-TG-HYD", headers=h, json={"settings": {"payment_methods": ["upi"]}})
    assert r.status_code == 200
    d = (await client.get("/api/v1/markets/cities/IN-TG-HYD", headers=h)).json()
    assert {s["key"]: s for s in d["effective_settings"]}["payment_methods"]["source"] == "Hyderabad"
    await client.patch("/api/v1/markets/cities/IN-TG-HYD", headers=h, json={"settings": {"payment_methods": None}})
    d = (await client.get("/api/v1/markets/cities/IN-TG-HYD", headers=h)).json()
    assert {s["key"]: s for s in d["effective_settings"]}["payment_methods"]["source"] == "India"

    r = await client.patch("/api/v1/markets/cities/IN-TG-HYD", headers=h, json={"settings": {"currency": "USD"}})
    assert r.status_code == 409 and "Only the country" in r.text

    ops_boi = await auth(client, "ops.boi@example.com")
    assert (await client.get("/api/v1/markets/cities/IN-TG-HYD", headers=ops_boi)).status_code == 403


# ── launching a city ──────────────────────────────────────────────────────────

async def test_country_manager_launches_a_city(client: AsyncClient) -> None:
    h = await auth(client, "cm.in@example.com")
    code = f"IN-TG-{rand()}"
    r = await client.post("/api/v1/markets/regions/IN-TG/cities", headers=h,
                          json={"code": code, "name": f"Testpur {code[-3:]}", "center_lat": 17.25, "center_lng": 80.15})
    assert r.status_code == 201, r.text

    r = await client.patch(f"/api/v1/markets/cities/{code}", headers=h, json={"status": "live"})
    assert r.status_code == 409
    assert "no zones are drawn" in r.text and "service hours are not set" in r.text

    r = await client.post(f"/api/v1/markets/cities/{code}/zones", headers=h,
                          json={"name": "Centre", "polygon": box(17.25, 80.15), "min_order": "99"})
    assert r.status_code == 201, r.text
    zone = r.json()
    assert zone["status"] == "draft" and zone["area_km2"] > 4

    r = await client.post(f"/api/v1/markets/cities/{code}/zones", headers=h,
                          json={"name": "Centre", "polygon": box(17.27, 80.15)})
    assert r.status_code == 409  # same name

    await client.patch(f"/api/v1/markets/zones/{zone['id']}", headers=h, json={"status": "live"})
    await client.patch(f"/api/v1/markets/cities/{code}", headers=h, json={"service_hours": {"open": "08:00", "close": "22:00"}})
    r = await client.patch(f"/api/v1/markets/cities/{code}", headers=h, json={"status": "live"})
    assert r.status_code == 200, r.text

    r = (await client.get("/api/v1/markets/locate", params={"lat": 17.25, "lng": 80.15})).json()
    assert r["serviceable"] and r["city_code"] == code

    # Redraw the zone away from the point: no longer served there.
    r = await client.patch(f"/api/v1/markets/zones/{zone['id']}", headers=h, json={"polygon": box(17.3, 80.2)})
    assert r.status_code == 200
    r = (await client.get("/api/v1/markets/locate", params={"lat": 17.25, "lng": 80.15})).json()
    assert not r["serviceable"]


async def test_bad_shapes_are_refused(client: AsyncClient) -> None:
    h = await auth(client, "cm.in@example.com")
    bowtie = {"type": "Polygon", "coordinates": [[[78.38, 17.44], [78.40, 17.46], [78.40, 17.44], [78.38, 17.46], [78.38, 17.44]]]}
    r = await client.post("/api/v1/markets/cities/IN-TG-HYD/zones", headers=h, json={"name": f"Bow {rand()}", "polygon": bowtie})
    assert r.status_code == 409 and "crosses itself" in r.text
    swapped = box(78.39, 17.45)  # lat and lng the wrong way round
    r = await client.post("/api/v1/markets/cities/IN-TG-HYD/zones", headers=h, json={"name": f"Swap {rand()}", "polygon": swapped})
    assert r.status_code in (409, 422)
    open_ring = {"type": "Polygon", "coordinates": [[[78.38, 17.44], [78.40, 17.44], [78.40, 17.46]]]}
    r = await client.post("/api/v1/markets/cities/IN-TG-HYD/zones", headers=h, json={"name": f"Open {rand()}", "polygon": open_ring})
    assert r.status_code == 422


@pytest.mark.parametrize(("email", "city_parent", "status"), [
    ("cm.in@example.com", "US-ID", 403),       # other country
    ("ops.hyd@example.com", "IN-TG", 403),     # city ops can't add cities
    ("viewer@example.com", "IN-TG", 403),
    ("finance.in@example.com", "IN-TG", 403),
])
async def test_who_cannot_add_cities(client: AsyncClient, email, city_parent, status) -> None:
    h = await auth(client, email)
    r = await client.post(f"/api/v1/markets/regions/{city_parent}/cities", headers=h,
                          json={"code": f"{city_parent}-{rand()}", "name": "Nope", "center_lat": 17, "center_lng": 78})
    assert r.status_code == status


async def test_city_ops_pause_and_resume_their_zones_only(client: AsyncClient) -> None:
    ops = await auth(client, "ops.hyd@example.com")
    cm = await auth(client, "cm.in@example.com")
    d = (await client.get("/api/v1/markets/cities/IN-TG-HYD", headers=ops)).json()
    zone = next(z for z in d["zones"] if z["name"] == "Old City")

    r = await client.post(f"/api/v1/markets/zones/{zone['id']}/pause", headers=ops, json={"reason": "Heavy rain"})
    assert r.status_code == 200 and r.json()["status"] == "paused"
    r = (await client.get("/api/v1/markets/locate", params={"lat": 17.3616, "lng": 78.4747})).json()
    assert not r["serviceable"] and "Heavy rain" in r["reason"]
    r = await client.post(f"/api/v1/markets/zones/{zone['id']}/resume", headers=ops)
    assert r.status_code == 200 and r.json()["status"] == "live"

    # City ops can pause but not redraw or rename.
    r = await client.patch(f"/api/v1/markets/zones/{zone['id']}", headers=ops, json={"min_order": "199"})
    assert r.status_code == 403
    assert (await client.patch(f"/api/v1/markets/zones/{zone['id']}", headers=cm, json={"min_order": "99"})).status_code == 200

    boise = (await client.get("/api/v1/markets/cities/US-ID-BOI", headers=await auth(client, "ops.boi@example.com"))).json()
    r = await client.post(f"/api/v1/markets/zones/{boise['zones'][0]['id']}/pause", headers=ops, json={"reason": "Not mine"})
    assert r.status_code == 403


async def test_state_cannot_open_in_draft_country(client: AsyncClient) -> None:
    sup = await auth(client, "admin@example.com")
    code = "X" + random.choice("ABCDEFGHJKLMNPQRSTUVWY")
    r = await client.post("/api/v1/markets/countries", headers=sup, json={
        "code": code, "name": f"Testland {code}", "currency": "EUR", "locales": ["en-GB"], "timezone": "UTC",
        "phone_code": "+999", "payment_providers": ["stripe"], "tax_regime": "us_sales_tax",
    })
    assert r.status_code in (201, 409)
    region = f"{code}-{rand(2)}"
    r = await client.post(f"/api/v1/markets/countries/{code}/regions", headers=sup, json={"code": region, "name": "North"})
    assert r.status_code in (201, 409)
    r = await client.patch(f"/api/v1/markets/regions/{region}", headers=sup, json={"status": "live"})
    assert r.status_code == 409 and "still a draft" in r.text

    cm = await auth(client, "cm.in@example.com")
    r = await client.post("/api/v1/markets/countries", headers=cm, json={
        "code": "QQ", "name": "Qland", "currency": "EUR", "locales": ["en"], "timezone": "UTC",
        "phone_code": "+1", "payment_providers": ["stripe"], "tax_regime": "gst",
    })
    assert r.status_code == 403  # only super admins add countries
