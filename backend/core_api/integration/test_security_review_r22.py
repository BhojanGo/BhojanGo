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
