"""P18 on Postgres: the rider onboarding checklist, uploads, delivery proof
(PIN or photo), the week-so-far earnings and the richer dispatch info."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import PNG, assign, login, move, new_order, pay, upload, user_id

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


async def new_rider(country: str = "US") -> tuple[str, dict]:
    """A rider who has only verified their phone."""
    from core_api.modules.identity.models.user import User
    from core_api.modules.identity.service.security import create_access_token
    from shared.db import AsyncSessionLocal

    rid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(User(id=rid, email=f"new.rider.{rid.hex[:8]}@example.com", phone=f"+1208{rid.int % 10**7:07d}",
                    full_name="Jordan Lee", role="driver", country=country, is_phone_verified=True))
        await db.commit()
    token, _ = create_access_token(str(rid), None, "driver", country)
    return str(rid), {"Authorization": f"Bearer {token}"}


async def signed_get(client: AsyncClient, path: str):  # type: ignore[no-untyped-def]
    from shared import internal_auth

    return await client.get(path, headers=internal_auth.sign("GET", path, b""))


async def test_onboarding_checklist_to_ready(client: AsyncClient) -> None:
    rid, h = await new_rider()
    r = await client.get("/api/v1/riders/me/onboarding", headers=h)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["first_name"] == "Jordan" and o["ready"] is False and (o["done"], o["total"]) == (1, 5)
    steps = {s["key"]: s for s in o["steps"]}
    assert steps["identity"]["status"] == "done" and steps["licence"]["status"] == "needed"
    assert steps["licence"]["title"] == "Driver's licence" and steps["background_check"]["status"] == "waiting"
    assert steps["payout"]["required"] is False
    assert (await signed_get(client, f"/api/v1/internal/riders/{rid}/ready")).json()["ready"] is False

    # Somebody else's upload can't be used; a PDF can't be a door photo; a document can.
    _, other = await new_rider()
    theirs = (await upload(client, other, "rider_document")).json()["key"]
    r = await client.post("/api/v1/riders/me/documents", headers=h, json={"kind": "licence", "file_key": theirs})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "FILE_NOT_YOURS"
    r = await client.post("/api/v1/uploads", headers=h, data={"purpose": "delivery_proof"},
                          files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 415
    r = await client.post("/api/v1/uploads", headers=h, data={"purpose": "rider_document"},
                          files={"file": ("big.png", PNG + b"0" * (5 * 1024 * 1024), "image/png")})
    assert r.status_code == 413

    for kind in ("licence", "insurance"):
        key = (await upload(client, h, "rider_document")).json()["key"]
        assert key.startswith(f"rider_document/{rid}/")
        r = await client.post("/api/v1/riders/me/documents", headers=h, json={"kind": kind, "file_key": key})
        assert r.status_code == 200, r.text
    steps = {s["key"]: s for s in r.json()["steps"]}
    assert steps["licence"]["status"] == steps["insurance"]["status"] == "in_review"
    assert steps["background_check"]["status"] == "in_review"  # starts once both are in

    # Admin review lands in P21; approve directly here.
    from sqlalchemy import update

    from core_api.modules.identity.models.rider import RiderDocument
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(update(RiderDocument).where(RiderDocument.rider_id == uuid.UUID(rid)).values(status="approved"))
        await db.commit()
    o = (await client.get("/api/v1/riders/me/onboarding", headers=h)).json()
    assert o["ready"] is True and o["done"] == 4  # the payout account is still to do, but doesn't block
    assert (await signed_get(client, f"/api/v1/internal/riders/{rid}/ready")).json() == {"rider_id": rid, "ready": True, "country": "US"}
    r = await client.post("/api/v1/riders/me/documents", headers=h, json={
        "kind": "licence", "file_key": (await upload(client, h, "rider_document")).json()["key"]})
    assert r.status_code == 409


async def test_seed_riders_are_ready(client: AsyncClient) -> None:
    h = await login(client, "rider1.hyd@example.com")
    o = (await client.get("/api/v1/riders/me/onboarding", headers=h)).json()
    assert o["ready"] is True and {s["key"] for s in o["steps"]} >= {"licence", "insurance", "background_check"}


async def test_delivery_needs_pin_or_own_photo_and_pin_is_customer_only(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)
    await pay(client, cust, order)
    partner = await login(client, "partner.hyd@example.com")
    for s in ("accepted", "preparing", "ready"):
        await move(client, partner, order["id"], s)
    rider, rider2 = await login(client, "rider1.hyd@example.com"), await login(client, "rider2.hyd@example.com")
    await assign(client, order["id"], rider)

    # What the rider is offered (internal dispatch info).
    info = (await signed_get(client, f"/api/v1/internal/orders/{order['id']}/dispatch")).json()
    assert info["rider_pay"] and info["currency"] == "INR" and info["items_count"] == 2 and info["bags"] == 1
    assert info["ready_in_minutes"] == 0 and info["drop_area"] == "Hyderabad" and info["code"].startswith("#")

    pin = (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()["pin"]
    assert pin and len(pin) == 4
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=rider)).json()["pin"] is None
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=partner)).json()["pin"] is None
    seen = (await client.get(f"/api/v1/orders/{order['id']}", headers=rider)).json()
    assert seen["customer"]["name"].endswith(".") and set(seen["delivery_address"]) == {"area", "city"}  # address after pickup
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()["customer"] is None
    await move(client, rider, order["id"], "picked_up")
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=rider)).json()["delivery_address"]["street"] == "Flat 302"

    url = f"/api/v1/orders/{order['id']}/status"
    r = await client.put(url, headers=rider, json={"status": "delivered"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PROOF_REQUIRED"
    wrong = f"{(int(pin) + 1) % 10000:04d}"
    r = await client.put(url, headers=rider, json={"status": "delivered", "proof": {"method": "pin", "pin": wrong}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PIN_WRONG"
    theirs = (await upload(client, rider2)).json()["key"]  # another rider's photo
    r = await client.put(url, headers=rider, json={"status": "delivered", "proof": {"method": "photo", "photo_key": theirs}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PHOTO_REQUIRED"
    made_up = f"delivery_proof/{user_id(rider)}/{uuid.uuid4()}.png"  # their prefix, but never uploaded
    r = await client.put(url, headers=rider, json={"status": "delivered", "proof": {"method": "photo", "photo_key": made_up}})
    assert r.status_code == 422
    r = await client.put(url, headers=rider, json={"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    assert r.status_code == 200 and r.json()["status"] == "delivered", r.text
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()["pin"] is None  # done with it

    from core_api.modules.orders.models.order import Order
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        proof = (await db.get(Order, uuid.UUID(order["id"]))).delivery_proof
    assert proof["method"] == "pin" and "pin" not in proof


async def test_week_so_far_for_a_rider(client: AsyncClient) -> None:
    rider = await login(client, "rider1.hyd@example.com")
    r = await client.get("/api/v1/finance/earnings/me", headers=rider)
    assert r.status_code == 200, r.text
    w = r.json()
    assert w["currency"] == "INR" and len(w["days"]) == 7 and w["payout_date"] == w["period_end"]
    assert set(w["summary"]) >= {"deliveries", "tips", "active_hours", "hourly_floor", "floor_top_up", "total"}
    assert w["summary"]["deliveries"] >= 1  # the test above delivered one this week
    assert w["city"] == "IN-TG-HYD" and w["summary"]["hourly_floor"] == "120"
    line = next(ln for d in [w["today"]] for ln in d["lines"])
    assert line["restaurant_name"] == "Spice Route Kitchen" and line["drop_area"] == "Hyderabad"


async def test_new_rider_week_uses_their_countrys_city(client: AsyncClient) -> None:
    _, h = await new_rider("US")
    w = (await client.get("/api/v1/finance/earnings/me", headers=h)).json()
    assert w["city"] == "US-ID-BOI" and w["summary"]["hourly_floor"] == "15" and w["summary"]["deliveries"] == 0


async def test_today_counts_only_completed_deliveries(client: AsyncClient) -> None:
    """The rider's "Today" (drive screen pill, earnings screen) is completed deliveries plus
    tips, nothing else: an offer, an accepted order on its way, or a cancelled one never
    moves it. (Offers live in realtime and never reach finance; this pins every state an
    order passes through on core_api's side.)"""
    from decimal import Decimal

    cust = await login(client, "customer2.hyd@example.com")
    partner = await login(client, "partner.hyd@example.com")
    rider = await login(client, "rider2.hyd@example.com")
    ops = await login(client, "ops.hyd@example.com", "BhojanGoAdmin1")

    async def today() -> tuple[Decimal, int]:
        w = (await client.get("/api/v1/finance/earnings/me", headers=rider)).json()
        return Decimal(w["today"]["total"]), len(w["today"]["lines"])

    before = await today()
    # Cooking and offered: nothing assigned to the rider yet.
    order = await new_order(client, cust)
    await pay(client, cust, order)
    for s in ("accepted", "preparing", "almost_ready"):
        await move(client, partner, order["id"], s)
    assert await today() == before
    # Accepted (the offer became an assignment) and picked up: still not earned.
    assert (await assign(client, order["id"], rider)).status_code == 200
    assert await today() == before
    await move(client, partner, order["id"], "ready")
    await move(client, rider, order["id"], "picked_up")
    assert await today() == before
    # Delivered: today goes up by exactly that delivery's line (base + distance + wait + tip).
    pin = (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()["pin"]
    r = await client.put(f"/api/v1/orders/{order['id']}/status", headers=rider,
                         json={"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    assert r.status_code == 200, r.text
    after = await today()
    w = (await client.get("/api/v1/finance/earnings/me", headers=rider)).json()
    line = next(ln for ln in w["today"]["lines"] if ln["order_id"] == order["id"])
    assert after == (before[0] + Decimal(line["total"]), before[1] + 1)
    assert Decimal(line["total"]) == sum(Decimal(line[k]) for k in ("base", "distance", "waiting", "tip"))
    # An order assigned and then cancelled never counts.
    other = await new_order(client, cust)
    await pay(client, cust, other)
    for s in ("accepted", "preparing", "almost_ready"):
        await move(client, partner, other["id"], s)
    assert (await assign(client, other["id"], rider)).status_code == 200
    r = await client.post(f"/api/v1/orders/{other['id']}/cancel", headers=ops, json={"reason": "other", "note": "test"})
    assert r.status_code == 200, r.text
    assert await today() == after
