"""R8 F10 on Postgres: Terms and Privacy per country from the seed, the English
fallback and the notice for a country without documents, versions (publishing
supersedes, history kept), who may edit and publish, the audit log, and the
acceptance records every sign-up path writes."""
import os
import random

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN_PW = "BhojanGoAdmin1"
BODY = "## 1. Section\n\nEnough words in this test document to publish it.\n\n## 2. Another\n\nMore words."


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def acceptances(user_id: str) -> list[tuple[str, str, int, str]]:
    import uuid

    from sqlalchemy import select

    from core_api.modules.legal.models import LegalAcceptance
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(LegalAcceptance).where(LegalAcceptance.user_id == uuid.UUID(user_id)))).scalars()
        return sorted((a.kind, a.country, a.version, a.source) for a in rows)


async def new_number(client: AsyncClient, country: str = "IN", ua: str = "okhttp/4.12.0") -> dict:
    phone = f"+9190000{random.randint(10000, 99999)}" if country == "IN" else f"+120855{random.randint(10000, 99999)}"
    assert (await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": country})).status_code == 200
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": country},
                          headers={"User-Agent": ua})
    assert r.status_code == 200 and r.json()["is_new_user"], r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "id": r.json()["user"]["id"]}


async def publish(client: AsyncClient, h: dict, kind: str, country: str, language: str = "en", title: str = "Test") -> dict:
    r = await client.post("/api/v1/admin/legal/documents", headers=h, json={
        "kind": kind, "country": country, "language": language, "title": title, "key_points": ["One point"], "body": BODY})
    assert r.status_code == 201, r.text
    r = await client.post(f"/api/v1/admin/legal/documents/{r.json()['document']['id']}/publish", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_seeded_documents_and_the_fallbacks(client: AsyncClient) -> None:
    for country in ("IN", "US"):
        for kind in ("terms", "privacy"):
            d = (await client.get(f"/api/v1/legal/{kind}", params={"country": country})).json()
            assert d["status"] == "published" and d["version"] >= 1 and d["country"] == country, d
            assert len(d["key_points"]) >= 3 and d["body"].count("\n## ") >= 8 and d["effective_date"]
            assert {"IN", "US"} <= set(d["available_countries"])
    privacy_in = (await client.get("/api/v1/legal/privacy", params={"country": "in"})).json()["body"]
    assert "Grievance Officer" in privacy_in and "[To be appointed]" in privacy_in and "Nominate" in privacy_in
    privacy_us = (await client.get("/api/v1/legal/privacy", params={"country": "US"})).json()["body"]
    assert "Do Not Sell or Share" in privacy_us and "California" in privacy_us
    # Another language falls back to English; a country without documents gets the notice, not a 404.
    te = (await client.get("/api/v1/legal/terms", params={"country": "IN", "language": "te"})).json()
    assert (te["language"], te["requested_language"], te["status"]) == ("en", "te", "published")
    gb = (await client.get("/api/v1/legal/terms", params={"country": "GB"})).json()
    assert gb["status"] == "unavailable" and gb["version"] is None and gb["notice"] and "IN" in gb["available_countries"]
    assert (await client.get("/api/v1/legal/terms/versions", params={"country": "GB"})).json()["versions"] == []
    assert (await client.get("/api/v1/legal/terms/versions/1", params={"country": "GB"})).status_code == 404
    assert (await client.get("/api/v1/legal/cookies", params={"country": "IN"})).status_code == 422


async def test_publishing_supersedes_and_keeps_the_history(client: AsyncClient) -> None:
    root = await login(client, "admin@example.com", ADMIN_PW)
    first = await publish(client, root, "terms", "ZZ", title="ZZ terms one")
    second = await publish(client, root, "terms", "ZZ", title="ZZ terms two")
    assert second["document"]["version"] == first["document"]["version"] + 1
    v = second["document"]["version"]
    cur = (await client.get("/api/v1/legal/terms", params={"country": "ZZ"})).json()
    assert (cur["version"], cur["title"], cur["status"]) == (v, "ZZ terms two", "published")
    hist = (await client.get("/api/v1/legal/terms/versions", params={"country": "ZZ"})).json()["versions"]
    assert [h["version"] for h in hist][:2] == [v, v - 1] and hist[1]["status"] == "superseded" and hist[1]["superseded_at"]
    old = (await client.get(f"/api/v1/legal/terms/versions/{v - 1}", params={"country": "ZZ"})).json()
    assert (old["status"], old["title"], old["current_version"]) == ("superseded", "ZZ terms one", v)
    # Published versions can't be edited, published again or discarded.
    pid = second["document"]["id"]
    assert (await client.patch(f"/api/v1/admin/legal/documents/{pid}", headers=root, json={"title": "x"})).status_code == 409
    assert (await client.post(f"/api/v1/admin/legal/documents/{pid}/publish", headers=root)).status_code == 409
    assert (await client.delete(f"/api/v1/admin/legal/documents/{pid}", headers=root)).status_code == 409


async def test_who_may_edit_and_publish_and_the_audit_log(client: AsyncClient) -> None:
    cm_in = await login(client, "cm.in@example.com", ADMIN_PW)
    # A Hindi draft of India's privacy notice: create, edit, publish.
    r = await client.post("/api/v1/admin/legal/documents", headers=cm_in, json={"kind": "privacy", "country": "IN", "language": "hi"})
    if r.status_code == 409:  # a rerun on the same database: discard the old draft first
        old = next(d for d in (await client.get("/api/v1/admin/legal/documents", headers=cm_in, params={
            "country": "IN", "kind": "privacy", "language": "hi"})).json() if d["status"] == "draft")
        assert (await client.delete(f"/api/v1/admin/legal/documents/{old['id']}", headers=cm_in)).status_code == 204
        r = await client.post("/api/v1/admin/legal/documents", headers=cm_in, json={"kind": "privacy", "country": "IN", "language": "hi"})
    assert r.status_code == 201, r.text
    draft = r.json()["document"]
    assert draft["status"] == "draft" and draft["version"] is None and draft["can_edit"] and len(draft["body"]) > 1000
    did = draft["id"]
    for who, email in (("cm_us", "cm.us@example.com"), ("viewer", "viewer@example.com"), ("ops", "ops.hyd@example.com")):
        h = await login(client, email, ADMIN_PW)
        assert (await client.patch(f"/api/v1/admin/legal/documents/{did}", headers=h, json={"title": "No"})).status_code in (403, 404), who
        assert (await client.post(f"/api/v1/admin/legal/documents/{did}/publish", headers=h)).status_code in (403, 404), who
        assert (await client.post("/api/v1/admin/legal/documents", headers=h, json={"kind": "terms", "country": "IN"})).status_code == 403, who
    viewer = await login(client, "viewer@example.com", ADMIN_PW)
    listed = (await client.get("/api/v1/admin/legal/documents", headers=viewer, params={"country": "IN"})).json()
    assert any(d["id"] == did for d in listed) and not any(d["can_edit"] for d in listed)
    customer = await login(client, "customer1.hyd@example.com")
    assert (await client.get("/api/v1/admin/legal/documents", headers=customer)).status_code == 403

    r = await client.patch(f"/api/v1/admin/legal/documents/{did}", headers=cm_in, json={
        "title": "गोपनीयता सूचना", "key_points": ["  एक  ", ""], "effective_date": "2026-12-01", "summary_of_changes": "Hindi"})
    assert r.status_code == 200 and r.json()["document"]["key_points"] == ["एक"], r.text
    r = await client.post(f"/api/v1/admin/legal/documents/{did}/publish", headers=cm_in)
    assert r.status_code == 200 and r.json()["document"]["status"] == "published", r.text
    actions = [e["action"] for e in r.json()["history"]]
    assert actions[:3] == ["legal.draft_created", "legal.draft_edited", "legal.published"]
    assert r.json()["history"][0]["actor"] == "India Country Manager"
    hi = (await client.get("/api/v1/legal/privacy", params={"country": "IN", "language": "hi"})).json()
    assert (hi["language"], hi["title"], str(hi["effective_date"])) == ("hi", "गोपनीयता सूचना", "2026-12-01")
    en = (await client.get("/api/v1/legal/privacy", params={"country": "IN", "language": "en"})).json()
    assert en["language"] == "en" and en["title"] == "Privacy notice"


async def test_every_sign_up_path_records_acceptance(client: AsyncClient) -> None:
    terms_in = (await client.get("/api/v1/legal/terms", params={"country": "IN"})).json()["version"]
    privacy_in = (await client.get("/api/v1/legal/privacy", params={"country": "IN"})).json()["version"]
    # Phone sign-up (a new number), from a browser.
    h = await new_number(client, ua="Mozilla/5.0 (X11; Linux x86_64)")
    assert await acceptances(h["id"]) == [("privacy", "IN", privacy_in, "web"), ("terms", "IN", terms_in, "web")]
    # Email sign-up (the emailed code creates the account), from an app.
    email = f"legal.{random.randint(10000, 99999)}@example.com"
    r = await client.post("/api/v1/auth/email/sign-up", headers={"User-Agent": "okhttp/4.12.0"}, json={
        "email": email, "password": "Long-enough-pass1", "full_name": "Legal Email", "country": "US"})
    assert r.status_code == 202, r.text
    r = await client.post("/api/v1/auth/email/verify", headers={"User-Agent": "okhttp/4.12.0"}, json={"email": email, "code": "123456"})
    assert r.status_code == 200, r.text
    assert [(k, c, s) for k, c, _, s in await acceptances(r.json()["user"]["id"])] == [("privacy", "US", "app"), ("terms", "US", "app")]

    # Delivery and kitchen partner terms, once published for India, are accepted when applying.
    root = await login(client, "admin@example.com", ADMIN_PW)
    dp = (await publish(client, root, "delivery_partner_terms", "IN", title="Delivery partner terms"))["document"]["version"]
    kp = (await publish(client, root, "kitchen_partner_terms", "IN", title="Kitchen partner terms"))["document"]["version"]
    rider = await new_number(client)
    r = await client.post("/api/v1/riders/apply", headers={"Authorization": rider["Authorization"]},
                          json={"full_name": "Legal Rider", "city_code": "IN-TG-HYD"})
    assert r.status_code == 200, r.text
    assert ("delivery_partner_terms", "IN", dp, "app") in await acceptances(rider["id"])
    kitchen = await new_number(client)
    r = await client.post("/api/v1/restaurants/apply", headers={"Authorization": kitchen["Authorization"]}, json={
        "full_name": "Legal Kitchen", "kitchen_name": "Legal Kitchen", "city_code": "IN-TG-HYD", "street": "Plot 1, Road 2",
        "area": "Madhapur", "zip": "500081", "lat": 17.44, "lng": 78.39, "cuisines": ["Thali"]})
    assert r.status_code == 201, r.text
    assert ("kitchen_partner_terms", "IN", kp, "app") in await acceptances(kitchen["id"])
    assert len(await acceptances(kitchen["id"])) == 3
    # A new kitchen by email (/kitchens/apply, then the emailed code): Terms, Privacy and the kitchen partner terms, once each.
    from core_api.integration.test_signup import _signup

    body = _signup()
    assert (await client.post("/api/v1/kitchens/apply", json=body, headers={"User-Agent": "Mozilla/5.0"})).status_code == 202
    r = await client.post("/api/v1/auth/email/verify", json={"email": body["email"], "code": "123456"}, headers={"User-Agent": "Mozilla/5.0"})
    assert r.status_code == 200, r.text
    got = await acceptances(r.json()["user"]["id"])
    assert sorted(k for k, *_ in got) == ["kitchen_partner_terms", "privacy", "terms"] and {s for *_, s in got} == {"web"}, got


async def test_updated_terms_notice_once(client: AsyncClient) -> None:
    rider = await new_number(client)
    r = await client.post("/api/v1/riders/apply", headers={"Authorization": rider["Authorization"]},
                          json={"full_name": "Notice Rider", "city_code": "IN-TG-HYD"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/api/v1/me/legal/pending", headers=h)).json() == []
    root = await login(client, "admin@example.com", ADMIN_PW)
    v = (await publish(client, root, "delivery_partner_terms", "IN", title="Delivery partner terms, updated"))["document"]["version"]
    pending = (await client.get("/api/v1/me/legal/pending", headers=h)).json()
    assert [(p["kind"], p["version"]) for p in pending] == [("delivery_partner_terms", v)]
    r = await client.post("/api/v1/me/legal/accept", headers={**h, "User-Agent": "Mozilla/5.0"}, json={"kinds": ["delivery_partner_terms"]})
    assert r.json() == [{"kind": "delivery_partner_terms", "version": v}]
    assert (await client.get("/api/v1/me/legal/pending", headers=h)).json() == []
    assert (await client.post("/api/v1/me/legal/accept", headers=h, json={"kinds": ["delivery_partner_terms"]})).json() == []
    assert (await client.get("/api/v1/me/legal/pending")).status_code in (401, 403)
