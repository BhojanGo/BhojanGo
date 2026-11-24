"""Web v2: everything the website shows about places comes from Markets data
(docs/design/web/WebDataRules.html), against a migrated, seeded database.

    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration/test_web_v2.py -v
"""
import os
import random
import string

import pytest
from httpx import ASGITransport, AsyncClient
from core_api.modules.identity.tests.signin import login_response

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
    r = await login_response(client, "admin@example.com", ADMIN_PW)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def email() -> str:
    return "w" + "".join(random.choices(string.ascii_lowercase, k=8)) + "@example.com"


async def test_directory_lists_live_and_soon_cities_only(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/markets/directory")).json()
    cities = {c["code"]: (k["code"], r["name"], c) for k in d["countries"] for r in k["regions"] for c in r["cities"]}
    assert cities["IN-TG-HYD"][2]["status"] == "live" and cities["IN-TG-HYD"][2]["path"] == "/in/hyderabad"
    assert cities["IN-TG-HYD"][2]["restaurants"] >= 1
    assert cities["US-ID-BOI"][2]["status"] == "live" and cities["US-ID-BOI"][2]["beta"] is False  # R27: live, not beta
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
        "country": None, "place": None, "region": None, "region_code": None, "city_code": None, "city_name": None,
        "city_path": None, "served": False}


async def test_hint_names_the_ip_place_served_or_not(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """R8: the IP's own town is shown as itself ("Meridian, ID"); "served" and the city only
    inside an open zone; a country we don't list names nothing."""
    from shared import client_ip as cip
    from shared import geoip

    boise = (await client.get("/api/v1/markets/areas", params={"q": "boise", "country": "US"})).json()
    inside = next(a for a in boise if a["served"])
    spots = {
        "203.0.113.1": geoip.Place("US", "Boise", "Idaho", inside["lat"], inside["lng"]),
        "203.0.113.2": geoip.Place("US", "Challis", "Idaho", 44.50, -114.23),  # Idaho, far from every zone
        "203.0.113.3": geoip.Place("GB", "London", "England", 51.5, -0.12),
    }
    monkeypatch.setattr(geoip, "lookup", lambda ip: spots.get(ip))
    monkeypatch.setattr(cip, "client_ip", lambda request: request.headers.get("x-test-ip", ""))

    def at(ip: str) -> dict:
        return {"x-test-ip": ip}

    served = (await client.get("/api/v1/markets/hint", headers=at("203.0.113.1"))).json()
    assert served["place"] == "Boise" and served["region_code"] == "ID" and served["served"] is True
    assert served["city_code"] == inside["city_code"] and served["city_path"] == inside["city_path"]
    away = (await client.get("/api/v1/markets/hint", headers=at("203.0.113.2"))).json()
    assert away["country"] == "US" and away["place"] == "Challis" and away["region_code"] == "ID"
    assert away["served"] is False and away["city_code"] is None and away["city_path"] is None
    abroad = (await client.get("/api/v1/markets/hint", headers=at("203.0.113.3"))).json()
    assert abroad["country"] is None and abroad["place"] is None and abroad["served"] is False


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
    # R37: Hyderabad's launch offer is paid for by BhojanGo, so it is off in the seed (no offer budget): no card shows it
    assert all(o["funded_by"] == "restaurant" for o in d["offers"]) and spice["offer"] is None
    assert all(c["count"] >= 2 for c in d["cuisines"])  # a cuisine needs two kitchens (web v3)
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


def _percentages(amounts: list[float]) -> list[int]:
    """Whole percentages by largest remainder (as the website's fairShares): a share
    below zero counts as nothing."""
    amounts = [max(a, 0.0) for a in amounts]
    exact = [a / sum(amounts) * 100 for a in amounts]
    pct = [int(x) for x in exact]
    for i in sorted(range(len(pct)), key=lambda i: (-(exact[i] - int(exact[i])), i))[:100 - sum(pct)]:
        pct[i] += 1
    return pct


@pytest.mark.parametrize("city", ["IN-TG-HYD", "US-ID-BOI"])
async def test_example_bill_shares_rider_pay_and_tip(client: AsyncClient, city: str) -> None:
    """R7: "Who gets your money" counts the rider's pay (base + distance + wait, from the
    engine's split) plus the tip, not the tip alone; the four shares are the whole bill
    and their whole percentages add up to 100."""
    b = (await client.get("/api/v1/pricing/example", params={"city": city})).json()
    shares = {k: float(v) for k, v in b["shares"].items()}
    assert list(shares) == ["kitchen", "rider", "tax", "us"]
    assert abs(sum(shares.values()) - float(b["total"])) < 0.005, (shares, b["total"])
    tip = sum(float(ln["amount"]) for ln in b["lines"] if ln["code"] == "tip")
    assert shares["rider"] > tip, (shares, tip)  # the rider's pay is in it, not just the tip
    assert abs(shares["tax"] - sum(float(ln["amount"]) for ln in b["lines"] if ln["code"] == "tax")) < 0.005, (shares, b["lines"])
    pct = _percentages(list(shares.values()))
    assert sum(pct) == 100 and min(pct) >= 0 and pct[1] > 0, pct


async def test_admin_markets_and_the_website_agree_on_every_city(client: AsyncClient) -> None:
    """R27: one source for a city's public status. R26 saw Boise "beta" in admin Markets
    while the website listed it live; admin Markets now shows the website's status from
    the same rules (markets/service/website.py), and both must agree for every city."""
    d = (await client.get("/api/v1/markets/directory")).json()
    site = {c["code"]: ("beta" if c["beta"] else c["status"]) for k in d["countries"] for r in k["regions"] for c in r["cities"]}
    overview = (await client.get("/api/v1/markets", headers=await admin(client))).json()
    console = {c["code"]: c["website"] for k in overview for r in k["regions"] for c in r["cities"]}
    assert console, overview
    for code, shown in console.items():
        assert site.get(code, "hidden") == shown, (code, shown, site.get(code))
    assert console["US-ID-BOI"] == "live" and console["IN-TG-HYD"] == "live"


async def test_basque_corner_kitchen_has_its_paella_photo(client: AsyncClient) -> None:
    """R27: Boise's Basque Corner Kitchen had no photo; the library's seafood-paella is its own dish."""
    r = await client.get("/api/v1/restaurants/by-slug/basque-corner-kitchen-downtown")
    assert r.status_code == 200, r.text
    assert r.json()["cover_url"] == "/food/seafood-paella-1600.webp", r.json().get("cover_url")
