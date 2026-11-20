"""R22 security review (docs/launch/security-review.md): the Medium findings about money
and photos, each failing without its fix.

S11  A kitchen's own offer had no ceiling on its amount off or weekly cap: a kitchen
     working with a customer could take its statement below zero. Now the Markets
     setting kitchen_offer_ceiling (country -> state -> city) bounds it.
S12  A bulk refund ran with no second admin whenever every order was under the city's
     per-order limit, whatever the total. Now the batch total is capped too.
S13  image_url, logo_url and cover_url took any string (another site, javascript:).
     Now only our own uploads (the caller's or the kitchen owner's), the food library
     or our photo host.
"""
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login
from core_api.integration.test_payments_refunds import client, delivered_order  # noqa: F401 - fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

ADMIN = "BhojanGoAdmin1"


async def _spice(client: AsyncClient) -> tuple[str, str]:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    return rest["id"], next(i["id"] for c in menu["categories"] for i in c["items"])


async def _end_offers(client: AsyncClient, rid: str, h: dict, prefix: str) -> None:
    for o in (await client.get(f"/api/v1/restaurants/{rid}/offers", headers=h)).json():
        if o["name"].startswith(prefix):
            await client.post(f"/api/v1/restaurants/{rid}/offers/{o['id']}/end", headers=h)


# ── S11: kitchen offer ceiling ─────────────────────────────────────────────────

async def test_a_kitchen_offer_above_its_markets_ceiling_is_refused(client: AsyncClient) -> None:  # noqa: F811
    partner = await login(client, "partner.hyd@example.com")
    cm = await login(client, "cm.in@example.com", ADMIN)
    rid, _ = await _spice(client)
    name = "R22 ceiling"
    try:
        # India's ceiling (seed: ₹200 off an order, ₹25,000 a week): far above it is refused
        r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
            "template": "flat_off", "name": f"{name} big", "amount": "5000", "weekly_cap": "100"})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "OFFER_OVER_CEILING", r.text
        r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
            "template": "free_delivery", "name": f"{name} cap", "weekly_cap": "10000000"})
        assert r.status_code == 422, r.text
        # a percent off with no maximum of its own gets the market's
        r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
            "template": "percent_off", "name": f"{name} pct", "percent": "50", "weekly_cap": "100"})
        assert r.status_code == 201, r.text
        pct = next(o for o in r.json() if o["name"] == f"{name} pct")
        assert Decimal(pct["params"]["max_discount"]) <= Decimal(200)

        # the city sets its own, lower: inherited key by key, enforced at once
        bad = await client.patch("/api/v1/markets/cities/IN-TG-HYD", headers=cm,
                                 json={"settings": {"kitchen_offer_ceiling": {"flat_off": "-5"}}})
        assert bad.status_code == 422, bad.text
        r = await client.patch("/api/v1/markets/cities/IN-TG-HYD", headers=cm,
                               json={"settings": {"kitchen_offer_ceiling": {"flat_off": "30"}}})
        assert r.status_code == 200, r.text
        r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
            "template": "flat_off", "name": f"{name} 40", "amount": "40", "weekly_cap": "100"})
        assert r.status_code == 422 and "30" in r.json()["detail"]["message"], r.text
    finally:
        await client.patch("/api/v1/markets/cities/IN-TG-HYD", headers=cm, json={"settings": {"kitchen_offer_ceiling": None}})
        await _end_offers(client, rid, partner, name)
    r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
        "template": "flat_off", "name": f"{name} 40", "amount": "40", "weekly_cap": "100"})
    try:
        assert r.status_code == 201, r.text  # back to India's ₹200
    finally:
        await _end_offers(client, rid, partner, name)


async def test_more_offers_dont_get_past_the_weekly_ceiling(client: AsyncClient) -> None:  # noqa: F811
    partner = await login(client, "partner.hyd@example.com")
    rid, _ = await _spice(client)
    name = "R22 stack"
    try:
        made = 0
        for _ in range(4):  # 4 x ₹9,000 a week is over India's ₹25,000 for the kitchen's offers together
            r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
                "template": "free_delivery", "name": f"{name} {made}", "weekly_cap": "9000", "min_subtotal": "999999"})
            if r.status_code != 201:
                break
            made += 1
        assert made < 4 and r.status_code == 422 and r.json()["detail"]["code"] == "OFFER_OVER_CEILING", r.text
    finally:
        await _end_offers(client, rid, partner, name)


# ── S12: bulk refund total ─────────────────────────────────────────────────────

async def test_many_small_refunds_over_the_total_need_a_second_admin(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    from core_api.modules.incidents import service as incidents

    ops = await login(client, "ops.hyd@example.com", ADMIN)
    finance = await login(client, "finance.in@example.com", ADMIN)
    cust = await login(client, "customer5.hyd@example.com")
    rid, _ = await _spice(client)
    start = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    for _ in range(2):
        await delivered_order(client, cust)
    pick = {"city": "IN-TG-HYD", "restaurant_id": rid, "placed_from": start,
            "placed_to": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(), "mode": "percent", "percent": "1"}
    # Hyderabad refunds up to ₹100 an order at once; for the test the batch's cap is a tiny share of that
    # (the default is 50 x), so 1% of two orders is over it while each order is far under ₹100.
    monkeypatch.setattr(incidents, "AUTO_TOTAL_TIMES", Decimal("0.0001"), raising=False)
    p = (await client.post("/api/v1/incidents/refunds/preview", headers=ops, json=pick)).json()
    assert p["count"] == 2 and all(o["amount"] < 10000 for o in p["orders"]), p
    assert p["needs_approval"] is True and p.get("approval_reasons") == ["total_over_limit"], p
    r = await client.post("/api/v1/incidents/refunds", headers=ops, json={**pick, "reason": "R22 test: total cap", "confirm": True})
    assert r.status_code == 200, r.text
    try:
        assert r.json()["status"] == "pending_approval", r.text
    finally:
        if r.json().get("status") == "pending_approval":
            await client.post(f"/api/v1/incidents/refunds/{r.json()['id']}/reject", headers=finance,
                              json={"note": "R22 test: not needed", "confirm": True})


# ── S13: photo addresses ───────────────────────────────────────────────────────

async def test_a_kitchen_cant_show_a_photo_from_another_site_or_account(client: AsyncClient) -> None:  # noqa: F811
    from core_api.integration.test_orders_flow import upload
    from core_api.integration.test_web_v3 import sql
    from shared.config import get_settings

    partner, other = await login(client, "partner.hyd@example.com"), await login(client, "partner.boi@example.com")
    rid, item = await _spice(client)
    menu = (await client.get(f"/api/v1/restaurants/{rid}/menu")).json()
    was_photo = next(i for c in menu["categories"] for i in c["items"] if i["id"] == item)["image_url"]
    was_cover = (await client.get(f"/api/v1/restaurants/{rid}")).json()["cover_url"]
    api = get_settings().payments.PUBLIC_API_URL.rstrip("/")
    theirs = (await upload(client, other, "menu_photo")).json()["public_path"]  # Boise's kitchen's own photo
    mine = (await upload(client, partner, "menu_photo")).json()["public_path"]
    try:
        for bad in ("javascript:alert(document.cookie)", "https://evil.example.com/pixel.gif", api + theirs, "x" * 600):
            r = await client.put(f"/api/v1/restaurants/{rid}/menu-items/{item}", headers=partner, json={"image_url": bad})
            assert r.status_code == 422, (bad[:40], r.text)
            r = await client.put(f"/api/v1/restaurants/{rid}", headers=partner, json={"cover_url": bad})
            assert r.status_code == 422, (bad[:40], r.text)
        r = await client.put(f"/api/v1/restaurants/{rid}/menu-items/{item}", headers=partner, json={"image_url": api + mine})
        assert r.status_code == 200 and r.json()["image_url"] == api + mine, r.text
    finally:
        await sql("UPDATE menu_items SET image_url = :u WHERE id = :i", u=was_photo, i=uuid.UUID(item))
        await sql("UPDATE restaurants SET cover_url = :u WHERE id = :i", u=was_cover, i=uuid.UUID(rid))


# ── S8: browser sessions in httpOnly cookies, CSRF, socket tickets ─────────────
# The website (X-Session: web) and the console (X-Session: admin, after its second step)
# get httpOnly cookies and no tokens in the body; a cookie counts only with that header;
# a change needs our own Origin; a socket ticket opens WebSockets only; signing out ends it.
# The apps' sign-in (no header) is unchanged. Cookies go in by hand: the test client talks
# plain http, where a Secure cookie is never sent back on its own.

WEB_PAGE = {"X-Session": "web", "Origin": "http://localhost:3000"}
CONSOLE = {"X-Session": "admin", "Origin": "http://localhost:3001"}


def _set_cookies(r) -> dict[str, str]:  # type: ignore[no-untyped-def]
    out = {}
    for c in r.headers.get_list("set-cookie"):
        name, rest = c.split("=", 1)
        out[name] = rest.split(";", 1)[0]
        assert "HttpOnly" in c and "Secure" in c and "SameSite=Lax" in c, c
    return out


def _jar(**cookies: str) -> dict:
    return {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}


async def test_the_website_session_is_in_httponly_cookies_not_the_page(client: AsyncClient) -> None:  # noqa: F811
    email = "customer3.hyd@example.com"
    r = await client.post("/api/v1/auth/login", headers=WEB_PAGE, json={"email": email, "password": "BhojanGo123"})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"] == "" and r.json()["refresh_token"] == "", "tokens handed to the page"
    got = _set_cookies(r)
    at, rt = got["bg_web_at"], got["bg_web_rt"]
    client.cookies.clear()
    me = await client.get("/api/v1/users/me", headers={"X-Session": "web", **_jar(bg_web_at=at)})
    assert me.status_code == 200 and me.json()["email"] == email, me.text
    # A change with the cookie alone (another site's form or script, no X-Session) is no session.
    r = await client.post("/api/v1/auth/socket-ticket", headers={"Origin": "http://localhost:3000", **_jar(bg_web_at=at)})
    assert r.status_code == 403, r.text
    # A change from another site's page, or with no origin at all, is refused (CSRF).
    for origin in ({"Origin": "https://evil.example"}, {}):
        r = await client.post("/api/v1/auth/socket-ticket", headers={"X-Session": "web", **origin, **_jar(bg_web_at=at)})
        assert r.status_code == 403 and r.json()["detail"]["code"] == "CSRF", r.text
    # The socket ticket: the realtime socket's key, refused by every API route.
    r = await client.post("/api/v1/auth/socket-ticket", headers={**WEB_PAGE, **_jar(bg_web_at=at)})
    assert r.status_code == 200, r.text
    ticket = r.json()["ticket"]
    for path in ("/api/v1/users/me", "/api/v1/orders"):
        assert (await client.get(path, headers={"Authorization": f"Bearer {ticket}"})).status_code == 401, path
    # Refresh from the cookie: new cookies, still no tokens in the body.
    r = await client.post("/api/v1/auth/refresh", headers={**WEB_PAGE, **_jar(bg_web_rt=rt)})
    assert r.status_code == 200 and r.json()["access_token"] == "", r.text
    fresh = _set_cookies(r)
    assert fresh["bg_web_rt"] != rt
    # Sign out: the cookies are cleared and the session is over.
    r = await client.post("/api/v1/auth/logout", headers={**WEB_PAGE, **_jar(bg_web_at=fresh["bg_web_at"])})
    assert r.status_code == 200, r.text
    assert _set_cookies(r) == {"bg_web_at": "", "bg_web_rt": ""}
    r = await client.post("/api/v1/auth/refresh", headers={**WEB_PAGE, **_jar(bg_web_rt=fresh["bg_web_rt"])})
    assert r.status_code == 401, r.text
    client.cookies.clear()


async def test_the_console_signs_in_with_its_second_step_into_cookies(client: AsyncClient) -> None:  # noqa: F811
    from core_api.modules.identity.tests.signin import SEED_TOTP_SECRET, next_code, secrets_by_email

    email = "admin@example.com"
    r = await client.post("/api/v1/auth/login", headers=CONSOLE, json={"email": email, "password": ADMIN})
    assert r.status_code == 200 and r.json()["mfa_required"], r.text
    assert not r.headers.get_list("set-cookie"), "a session before the second step"
    challenge = r.json()
    assert not challenge["enrolment_required"], "the seed's admin has an authenticator"
    code = await next_code(email, secrets_by_email.get(email) or SEED_TOTP_SECRET)
    r = await client.post("/api/v1/auth/mfa/verify", headers=CONSOLE, json={"mfa_token": challenge["mfa_token"], "code": code})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"] == "" and r.json()["admin_roles"], r.json()
    at = _set_cookies(r)["bg_admin_at"]
    client.cookies.clear()
    r = await client.get("/api/v1/admin/me", headers={"X-Session": "admin", **_jar(bg_admin_at=at)})
    assert r.status_code == 200, r.text
    # The website's cookie name doesn't open the console's session, nor the other way round.
    assert (await client.get("/api/v1/admin/me", headers={"X-Session": "web", **_jar(bg_admin_at=at)})).status_code == 401
    await client.post("/api/v1/auth/logout", headers={**CONSOLE, **_jar(bg_admin_at=at)})
    client.cookies.clear()


async def test_the_apps_sign_in_is_unchanged(client: AsyncClient) -> None:  # noqa: F811
    r = await client.post("/api/v1/auth/login", json={"email": "customer3.hyd@example.com", "password": "BhojanGo123"})
    assert r.status_code == 200 and r.json()["access_token"] and r.json()["refresh_token"], r.text
    assert not r.headers.get_list("set-cookie")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.post("/api/v1/auth/socket-ticket", headers=h)).status_code == 200  # no Origin needed with a token
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": r.json()["refresh_token"]})
    assert r.status_code == 200 and r.json()["access_token"], r.text
