"""Web v2: everything the website shows about places comes from Markets data
(docs/design/web/WebDataRules.html), against a migrated, seeded database.

    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration/test_web_v2.py -v
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
ARABIAN_SEA = (15.0, 65.0)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def admin(client: AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def email() -> str:
    return "w" + "".join(random.choices(string.ascii_lowercase, k=8)) + "@example.com"


async def test_directory_lists_live_and_soon_cities_only(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/markets/directory")).json()
    cities = {c["code"]: (k["code"], r["name"], c) for k in d["countries"] for r in k["regions"] for c in r["cities"]}
    assert cities["IN-TG-HYD"][2]["status"] == "live" and cities["IN-TG-HYD"][2]["path"] == "/in/hyderabad"
    assert cities["IN-TG-HYD"][2]["restaurants"] >= 1
    assert cities["US-ID-BOI"][2]["status"] == "live" and cities["US-ID-BOI"][2]["beta"] is True
    # coming soon: listed (a draft state is fine), no kitchens counted
    assert cities["IN-AP-VSKP"][1] == "Andhra Pradesh" and cities["IN-AP-VSKP"][2]["status"] == "soon"
    assert cities["US-ID-NMP"][2]["status"] == "soon" and cities["US-ID-NMP"][2]["restaurants"] == 0
    assert "IN-TG-WGL" not in cities  # a draft city stays hidden
    india = next(k for k in d["countries"] if k["code"] == "IN")
    assert india["slug"] == "in" and india["currency"] == "INR" and "te-IN" in india["locales"]
    assert india["tax_regime"] == "gst" and "upi" in india["payment_methods"]
    assert d["totals"]["live"] >= 2 and d["totals"]["soon"] >= 3 and d["totals"]["countries"] >= 2


async def test_city_page_by_path(client: AsyncClient) -> None:
    c = (await client.get("/api/v1/markets/cities/in/hyderabad")).json()
    assert c["code"] == "IN-TG-HYD" and c["country"]["currency"] == "INR" and c["timezone"] == "Asia/Kolkata"
    assert any(z["name"] == "Madhapur" for z in c["zones"]) and not any(z["name"] == "Kokapet" for z in c["zones"])
    assert (await client.get("/api/v1/markets/cities/us/nampa")).json()["status"] == "soon"
    assert (await client.get("/api/v1/markets/cities/in/warangal")).status_code == 404
    assert (await client.get("/api/v1/markets/cities/us/hyderabad")).status_code == 404


async def test_areas_find_open_zones_and_soon_cities(client: AsyncClient) -> None:
    hits = (await client.get("/api/v1/markets/areas", params={"q": "madhap"})).json()
    assert hits[0]["label"] == "Madhapur, Hyderabad" and hits[0]["served"] is True and hits[0]["city_path"] == "/in/hyderabad"
    loc = (await client.get("/api/v1/markets/locate", params={"lat": hits[0]["lat"], "lng": hits[0]["lng"]})).json()
    assert loc["serviceable"] and loc["zone_name"] == "Madhapur"  # the point is inside its area
    assert not (await client.get("/api/v1/markets/areas", params={"q": "kokapet"})).json()  # a draft zone
    soon = (await client.get("/api/v1/markets/areas", params={"q": "namp"})).json()
    assert soon[0]["city_code"] == "US-ID-NMP" and soon[0]["served"] is False
    assert (await client.get("/api/v1/markets/areas", params={"q": "madhap", "country": "US"})).json() == []


async def test_hint_without_a_database_is_empty(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/markets/hint")).json() == {
        "country": None, "place": None, "region": None, "city_code": None, "city_name": None, "city_path": None,
        "served": False}


async def test_waitlist_and_demand(client: AsyncClient) -> None:
    h = await admin(client)
    before = (await client.get("/api/v1/markets/waitlist/demand", headers=h)).json()
    n0 = next((c["signups"] for c in before["cities"] if c["city_code"] == "US-ID-NMP"), 0)
    me = email()
    body = {"email": me, "city_code": "US-ID-NMP", "consent": True, "source": "soon_city", "locale": "en-US"}
    assert (await client.post("/api/v1/markets/waitlist", json=body)).status_code == 202
    assert (await client.post("/api/v1/markets/waitlist", json=body)).status_code == 202  # twice: one sign-up
    # an address outside every zone, counted for no city; a city typed by hand
    assert (await client.post("/api/v1/markets/waitlist", json={"email": me, "lat": ARABIAN_SEA[0], "lng": ARABIAN_SEA[1],
                                                                 "consent": True, "source": "outside_zone"})).status_code == 202
    town = "Twin Falls " + email()[:5]
    assert (await client.post("/api/v1/markets/waitlist", json={"email": me, "city_text": town, "consent": True,
                                                                 "source": "suggest_city"})).status_code == 202
    # no consent, unknown city, nothing to identify the place: refused
    assert (await client.post("/api/v1/markets/waitlist", json={**body, "consent": False})).status_code == 422
    assert (await client.post("/api/v1/markets/waitlist", json={**body, "city_code": "US-ID-XXX"})).status_code == 422
    assert (await client.post("/api/v1/markets/waitlist", json={"email": me, "consent": True})).status_code == 422
    # the apps' older form still works
    assert (await client.post("/api/v1/markets/waitlist", json={"phone": "+12085550177", "lat": 43.54, "lng": -116.56})).status_code == 202
    after = (await client.get("/api/v1/markets/waitlist/demand", headers=h)).json()
    nampa = next(c for c in after["cities"] if c["city_code"] == "US-ID-NMP")
    assert nampa["signups"] == n0 + 1 and nampa["with_consent"] >= 1 and nampa["status"] == "soon"
    assert any(s["text"] == town.lower() for s in after["suggested"])
    overview = (await client.get("/api/v1/markets", headers=h)).json()
    city = next(c for k in overview for r in k["regions"] for c in r["cities"] if c["code"] == "US-ID-NMP")
    assert city["waitlist"] == nampa["signups"]


async def test_discover_an_address(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/discover", params={"lat": MADHAPUR[0], "lng": MADHAPUR[1]})).json()
    assert d["served"] and d["currency"] == "INR" and d["city"]["path"] == "/in/hyderabad" and d["zone"] == "Madhapur"
    spice = next(k for k in d["restaurants"] if k["slug"] == "spice-route-kitchen-madhapur")
    assert spice["path"] == "/in/hyderabad/spice-route-kitchen-madhapur"
    assert float(spice["delivery_fee"]) > 0 and spice["distance"] is not None
    # Hyderabad's launch offer, paid for by the platform, on every Hyderabad kitchen
    launch = next(o for o in d["offers"] if o["template"] == "percent_off")
    assert launch["funded_by"] == "platform" and launch["percent"] == "10" and launch["restaurant"] is None
    assert spice["offer"]["id"] == launch["id"]
    assert {c["name"] for c in d["cuisines"]} and all(c["count"] >= 1 for c in d["cuisines"])
    # a whole city (its page): no per-address fees
    city = (await client.get("/api/v1/discover", params={"city": "IN-TG-HYD"})).json()
    assert city["served"] and len(city["restaurants"]) >= len(d["restaurants"]) and city["restaurants"][0]["delivery_fee"] is None
    # outside every zone
    sea = (await client.get("/api/v1/discover", params={"lat": ARABIAN_SEA[0], "lng": ARABIAN_SEA[1]})).json()
    assert sea["served"] is False and sea["restaurants"] == []


async def test_example_bill_for_a_city(client: AsyncClient) -> None:
    b = (await client.get("/api/v1/pricing/example", params={"city": "US-ID-BOI"})).json()
    assert b["currency"] == "USD" and b["source"] in ("order", "typical") and b["lines"][0]["code"] == "food"
    assert abs(sum(float(ln["amount"]) for ln in b["lines"]) - float(b["total"])) < 0.01
