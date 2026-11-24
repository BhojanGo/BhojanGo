"""P6 markets against a migrated, seeded PostGIS database (see test_migrated_db.py).

    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration -v
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
    r = await login_response(client, email, password)
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
    assert r["currency"] == "INR" and r["min_order"] == "0.00" and r["status"] == "live"  # R36: no zone minimum

    r = (await client.get("/api/v1/markets/locate", params={"lat": BOISE_DOWNTOWN[0], "lng": BOISE_DOWNTOWN[1]})).json()
    assert r["serviceable"] and r["city_code"] == "US-ID-BOI" and r["status"] == "live"  # R27: Boise is live

    r = (await client.get("/api/v1/markets/locate", params={"lat": KOKAPET_DRAFT[0], "lng": KOKAPET_DRAFT[1]})).json()
    assert not r["serviceable"] and "Hyderabad" in r["reason"]

    r = (await client.get("/api/v1/markets/locate", params={"lat": ARABIAN_SEA[0], "lng": ARABIAN_SEA[1]})).json()
    assert r == {**r, "serviceable": False, "reason": "We don't deliver here yet"}


async def test_state_short_codes_for_the_location_line(client: AsyncClient) -> None:
    """Round 20: "City, ST" everywhere. Every state has a short code (the seed's from the ISO code); the public
    directory, the city page and locate carry it; admin can set it; a new state without one gets the ISO code's
    second part; a bad one is refused."""
    d = (await client.get("/api/v1/markets/directory")).json()
    short = {rg["code"]: rg["short_code"] for k in d["countries"] for rg in k["regions"]}
    assert short["IN-TG"] == "TG" and short["US-ID"] == "ID", short
    page = (await client.get("/api/v1/markets/cities/in/hyderabad")).json()
    assert page["region"]["short_code"] == "TG"
    r = (await client.get("/api/v1/markets/locate", params={"lat": MADHAPUR[0], "lng": MADHAPUR[1]})).json()
    assert (r["region_code"], r["region_short_code"]) == ("IN-TG", "TG")

    h = await auth(client, "cm.in@example.com")
    code = f"IN-Q{rand(2)}"
    r = await client.post("/api/v1/markets/countries/IN/regions", headers=h, json={"code": code, "name": "Short Code Test"})
    assert r.status_code in (200, 201) and r.json()["short_code"] == code.split("-")[1], r.text
    r = await client.patch(f"/api/v1/markets/regions/{code}", headers=h, json={"short_code": "SC"})
    assert r.status_code == 200 and r.json()["short_code"] == "SC", r.text
    r = await client.patch(f"/api/v1/markets/regions/{code}", headers=h, json={"short_code": "far too long"})
    assert r.status_code == 422
    r = await client.post("/api/v1/markets/countries/IN/regions", headers=h,
                          json={"code": f"IN-Q{rand(2)}", "name": "Short Code Test 2", "short_code": "q1"})
    assert r.status_code == 422  # upper-case letters and digits only


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


async def test_sign_up_and_kitchens_follow_the_countries_table(client: AsyncClient) -> None:
    """No country list in the code: a draft country takes no sign-ups or kitchens, a
    kitchen charges in its country's currency, a phone carries its country's code."""
    sup = await auth(client, "admin@example.com")
    code = "Y" + random.choice("ABCDEFGHJKLMNPQRSTUVWXZ")
    r = await client.post("/api/v1/markets/countries", headers=sup, json={
        "code": code, "name": f"Draftland {code}", "currency": "EUR", "locales": ["en-GB"], "timezone": "UTC",
        "phone_code": "+998", "payment_providers": ["stripe"], "tax_regime": "gst"})
    assert r.status_code in (201, 409), r.text
    r = await client.post("/api/v1/auth/send-otp", json={"phone": "+998123456789", "country": code})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "COUNTRY_NOT_AVAILABLE", r.text
    r = await client.post("/api/v1/auth/send-otp", json={"phone": "+12085550199", "country": "IN"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PHONE_COUNTRY_MISMATCH", r.text

    partner = await auth(client, "partner.hyd@example.com", "BhojanGo123")
    kitchen = {"name": "Country Check Kitchen", "cuisine_types": ["Indian"], "city": "Hyderabad",
               "address": {"street": "1 Rd", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"},
               "location": {"lat": 17.44, "lng": 78.39}, "delivery_time_min": 20, "delivery_time_max": 40,
               "minimum_order_amount": 0, "delivery_fee": 0}
    r = await client.post("/api/v1/restaurants", headers=partner, json={**kitchen, "country": "IN", "currency": "USD"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "CURRENCY_MISMATCH", r.text
    r = await client.post("/api/v1/restaurants", headers=partner, json={
        **kitchen, "country": code, "currency": "EUR", "address": {**kitchen["address"], "country": code}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "COUNTRY_NOT_AVAILABLE", r.text


async def test_payment_methods_follow_the_payment_provider(client: AsyncClient) -> None:
    """R14: a country offers only what its payment providers take (Markets), and says so."""
    us_cm = await auth(client, "cm.us@example.com")
    us = next(c for c in (await client.get("/api/v1/markets", headers=us_cm)).json() if c["code"] == "US")
    assert us["payment_providers"] == ["stripe"] and us["payment_methods_supported"] == ["card", "apple_pay", "google_pay"]
    r = await client.patch("/api/v1/markets/countries/US", headers=us_cm, json={"settings": {"payment_methods": ["card", "upi"]}})
    assert r.status_code == 409 and "UPI isn't offered by Stripe" in r.text, r.text
    r = await client.patch("/api/v1/markets/countries/US", headers=us_cm, json={"settings": {"payment_methods": ["card", "apple_pay", "google_pay"]}})
    assert r.status_code == 200, r.text
    in_cm = await auth(client, "cm.in@example.com")
    india = (await client.patch("/api/v1/markets/countries/IN", headers=in_cm, json={"settings": {}})).json()
    assert india["payment_methods_supported"] == ["card", "upi", "wallet", "net_banking"]
    r = await client.patch("/api/v1/markets/countries/IN", headers=in_cm, json={"settings": {"payment_methods": ["upi", "apple_pay", "card"]}})
    assert r.status_code == 409 and "Apple Pay isn't offered by Razorpay" in r.text, r.text


async def test_hero_photo_is_a_country_setting(client: AsyncClient) -> None:
    """The website's landing hero per country (Markets -> country -> Hero dish): a photo
    library slug, validated, country-level only, on the public directory."""
    def heroes(d: dict) -> dict:
        return {k["code"]: k["hero_photo"] for k in d["countries"]}

    d = (await client.get("/api/v1/markets/directory")).json()
    assert heroes(d) == {**heroes(d), "IN": "south-indian-thali", "US": "pepperoni-pizza"}  # the seed's choices
    assert d["hero_photo"]  # the default, for a visitor outside every country

    cm = await auth(client, "cm.in@example.com")
    r = await client.patch("/api/v1/markets/countries/IN", headers=cm, json={"settings": {"hero_photo": "not-a-dish"}})
    assert r.status_code == 409 and "library" in r.text, r.text
    r = await client.patch("/api/v1/markets/countries/IN", headers=cm, json={"settings": {"hero_photo": "masala-dosa"}})
    assert r.status_code == 200 and r.json()["settings"]["hero_photo"] == "masala-dosa", r.text
    assert r.json()["settings"]["payment_methods"]  # other settings kept
    try:
        assert heroes((await client.get("/api/v1/markets/directory")).json())["IN"] == "masala-dosa"
        # another country's manager can't change it; a state can't override it
        r = await client.patch("/api/v1/markets/countries/IN", headers=await auth(client, "cm.us@example.com"),
                               json={"settings": {"hero_photo": "ramen"}})
        assert r.status_code == 403
        r = await client.patch("/api/v1/markets/regions/IN-TG", headers=cm, json={"settings": {"hero_photo": "ramen"}})
        assert r.status_code == 409 and "Only the country" in r.text
        # no choice: the default library photo
        r = await client.patch("/api/v1/markets/countries/IN", headers=cm, json={"settings": {"hero_photo": None}})
        assert r.status_code == 200 and "hero_photo" not in r.json()["settings"]
        d = (await client.get("/api/v1/markets/directory")).json()
        assert heroes(d)["IN"] == d["hero_photo"]
    finally:
        r = await client.patch("/api/v1/markets/countries/IN", headers=cm, json={"settings": {"hero_photo": "south-indian-thali"}})
        assert r.status_code == 200


async def test_an_open_country_only_lists_languages_we_translate(client: AsyncClient) -> None:
    """Round 5: the website, apps and messages have no words in a language we don't
    translate, so an open country can't list it (a draft one can, while it's set up)."""
    sup = await auth(client, "admin@example.com")
    r = await client.patch("/api/v1/markets/countries/US", headers=sup, json={"locales": ["en-US", "es-US", "fr-US"]})
    assert r.status_code == 409 and "fr-US" in r.text, r.text
    us = next(c for c in (await client.get("/api/v1/markets", headers=sup)).json() if c["code"] == "US")
    assert us["locales"] == ["en-US", "es-US"]


async def test_city_time_zones_inherit_from_region_then_country() -> None:
    """Order times are shown in their city's zone: the city's own, else its state's, else its country's."""
    from core_api.modules.markets.service.zones import city_time_zones
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        zones = await city_time_zones(db, ["IN-TG-HYD", "US-ID-BOI", "XX-NO-NE", None])
    assert zones == {"IN-TG-HYD": "Asia/Kolkata", "US-ID-BOI": "America/Boise"}


async def test_every_city_has_its_own_zone_and_the_us_pays_on_boise_time(client: AsyncClient) -> None:
    """R27: a city's zone is its own (Boise: America/Boise, not the US's New York); payout weeks are
    counted in the country's payout zone (US: America/Boise for now, India: Asia/Kolkata)."""
    sup = await auth(client, "admin@example.com")
    countries = {c["code"]: c for c in (await client.get("/api/v1/markets", headers=sup)).json()}
    us, india = countries["US"], countries["IN"]
    assert us["payout_timezone"] == "America/Boise" and us["payout_zone"] == "America/Boise"
    assert india["payout_zone"] == "Asia/Kolkata"
    cities = {c["code"]: c for k in (us, india) for r in k["regions"] for c in r["cities"]}
    assert cities["US-ID-BOI"]["timezone"] == "America/Boise" and cities["US-ID-NMP"]["timezone"] == "America/Boise"
    assert cities["IN-TG-HYD"]["timezone"] == "Asia/Kolkata"
    boise = (await client.get("/api/v1/markets/cities/US-ID-BOI", headers=sup)).json()
    tz = next(s for s in boise["effective_settings"] if s["key"] == "timezone")
    assert tz["value"] == "America/Boise" and tz["source_level"] == "city"

    # Not a time zone: refused, for a city and for the payout zone.
    r = await client.patch("/api/v1/markets/cities/US-ID-NMP", headers=sup, json={"timezone": "Mountain Time"})
    assert r.status_code == 422 and "IANA" in r.text, r.text
    r = await client.patch("/api/v1/markets/countries/US", headers=sup, json={"payout_timezone": "Boise time"})
    assert r.status_code == 422, r.text

    # A new city starts with its state's zone (Idaho: America/Boise), never left empty.
    code = f"US-ID-{rand()}"
    r = await client.post("/api/v1/markets/regions/US-ID/cities", headers=sup,
                          json={"code": code, "name": f"Testville {code[-3:]}", "center_lat": 43.6, "center_lng": -116.4})
    assert r.status_code == 201 and r.json()["timezone"] == "America/Boise", r.text


async def test_finance_weeks_are_in_the_payout_zone(client: AsyncClient) -> None:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    h = await auth(client, "admin@example.com")
    weeks = (await client.get("/api/v1/finance/payout-weeks", headers=h, params={"country": "US"})).json()
    assert weeks["timezone"] == "America/Boise", weeks
    assert weeks["today"] == datetime.now(UTC).astimezone(ZoneInfo("America/Boise")).date().isoformat()
