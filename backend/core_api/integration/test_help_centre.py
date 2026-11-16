"""F9 on Postgres: the Help centre. Public reads with the country/language
fallback and full-text search over the seeded articles; the admin console's
write, publish and unpublish with RBAC, versions and the audit log; helpful
votes and the contact form, both rate-limited; a signed-in message to support."""
import os
import uuid

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login, new_order  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
PW = "BhojanGoAdmin1"
H = "/api/v1/help"
OPS = "/api/v1/ops/help/articles"


@pytest.fixture(autouse=True)
def _reset_help_limits():
    from core_api.modules.content.api.v1.help_public import limiter

    limiter.reset()
    yield
    limiter.reset()


async def test_public_reads_fall_back_country_then_english_then_global(client: AsyncClient) -> None:  # noqa: F811
    home = (await client.get(H, params={"country": "IN", "language": "hi"})).json()
    assert {t["topic"] for t in home["topics"]} == {"orders", "payments-refunds", "delivery", "account", "kitchen-partners",
                                                   "delivery-partners"}
    assert all(t["count"] > 0 for t in home["topics"])
    assert home["popular"][0]["slug"] == "fair-bill-who-gets-your-money" and home["popular"][0]["language"] == "hi"

    # India in Hindi: India's own version, translated
    a = (await client.get(f"{H}/articles/ways-to-pay", params={"country": "IN", "language": "hi"})).json()
    assert (a["country"], a["language"], a["fallback"]) == ("IN", "hi", False)
    # India in Telugu: no Telugu yet, India's English version (and the page says so)
    a = (await client.get(f"{H}/articles/ways-to-pay", params={"country": "IN", "language": "te"})).json()
    assert (a["country"], a["language"], a["fallback"]) == ("IN", "en", True)
    # The US in Spanish: the US version
    a = (await client.get(f"{H}/articles/ways-to-pay", params={"country": "US", "language": "es"})).json()
    assert (a["country"], a["language"]) == ("US", "es") and "Stripe" in a["body"]
    # No country: the global articles only; a country-only article isn't there
    assert (await client.get(f"{H}/articles/ways-to-pay")).status_code == 404
    pin = (await client.get(f"{H}/articles/delivery-pin", params={"country": "US"})).json()
    assert pin["country"] == "*" and pin["related"] and all(r["slug"] != "delivery-pin" for r in pin["related"])

    topic = (await client.get(f"{H}/topics/kitchen-partners", params={"country": "US", "language": "en"})).json()
    docs = [x for x in topic["articles"] if x["slug"] == "kitchen-documents"]
    assert docs and docs[0]["country"] == "US"
    assert (await client.get(f"{H}/topics/nothing")).status_code == 404


async def test_search_finds_articles_as_you_type(client: AsyncClient) -> None:  # noqa: F811
    def slugs(r) -> list[str]:  # type: ignore[no-untyped-def]
        return [x["slug"] for x in r.json()["results"]]

    r = await client.get(f"{H}/search", params={"q": "PIN", "country": "IN", "language": "en"})
    assert "delivery-pin" in slugs(r)
    r = await client.get(f"{H}/search", params={"q": "refu", "country": "US", "language": "en"})
    assert "how-refunds-work" in slugs(r)
    # Reading in Hindi, typing English: still found, answered in Hindi
    r = await client.get(f"{H}/search", params={"q": "PIN", "country": "IN", "language": "hi"})
    hit = next(x for x in r.json()["results"] if x["slug"] == "delivery-pin")
    assert hit["language"] == "hi"
    for q in ("", "   ", "&|!:*", "'); drop table help_articles; --"):
        assert (await client.get(f"{H}/search", params={"q": q})).status_code == 200
    assert slugs(await client.get(f"{H}/search", params={"q": "zzzqqqxxyy"})) == []


async def test_admin_write_publish_history_audit_and_rbac(client: AsyncClient) -> None:  # noqa: F811
    cm_in = await login(client, "cm.in@example.com", PW)
    slug = f"test-article-{uuid.uuid4().hex[:8]}"
    body = {"slug": slug, "country": "IN", "language": "en", "topic": "orders", "title": "Testing the help desk",
            "summary": "A test", "body": "## Hello\n\nFirst words.", "related": ["delivery-pin"]}
    # Only the super admin writes help for every country.
    assert (await client.post(OPS, headers=cm_in, json={**body, "country": "*"})).status_code == 403
    r = await client.post(OPS, headers=cm_in, json=body)
    assert r.status_code == 201, r.text
    art = r.json()
    aid = art["id"]
    assert art["status"] == "draft" and art["can_edit"]
    assert (await client.post(OPS, headers=cm_in, json=body)).status_code == 409
    public = {"country": "IN", "language": "en"}
    assert (await client.get(f"{H}/articles/{slug}", params=public)).status_code == 404  # drafts aren't public

    # Read-only roles and other countries
    for who, code in (("support.hyd@example.com", 403), ("viewer@example.com", 403), ("cm.us@example.com", 404),
                      ("ops.hyd@example.com", 403)):
        h = await login(client, who, PW)
        assert (await client.patch(f"{OPS}/{aid}", headers=h, json={"title": "Hacked title"})).status_code == code, who
        assert (await client.post(f"{OPS}/{aid}/publish", headers=h)).status_code == code, who
    support = await login(client, "support.hyd@example.com", PW)
    seen = (await client.get(OPS, headers=support, params={"country": "IN", "q": slug})).json()
    assert [a["id"] for a in seen] == [aid] and seen[0]["can_edit"] is False
    assert any(a["country"] == "*" for a in (await client.get(OPS, headers=support, params={"country": "*"})).json())
    cm_us = await login(client, "cm.us@example.com", PW)
    assert aid not in {a["id"] for a in (await client.get(OPS, headers=cm_us)).json()}

    r = await client.post(f"{OPS}/{aid}/publish", headers=cm_in)
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert (await client.get(f"{H}/articles/{slug}", params=public)).json()["title"] == "Testing the help desk"
    # Saving a published article holds the change until it's published
    r = await client.patch(f"{OPS}/{aid}", headers=cm_in, json={"title": "Testing the help desk, again"})
    assert r.json()["draft"]["title"] == "Testing the help desk, again" and r.json()["live"]["title"] == "Testing the help desk"
    assert (await client.get(f"{H}/articles/{slug}", params=public)).json()["title"] == "Testing the help desk"
    changes = (await client.get(OPS, headers=cm_in, params={"status": "changes", "q": slug})).json()
    assert [a["id"] for a in changes] == [aid]
    await client.post(f"{OPS}/{aid}/publish", headers=cm_in)
    assert (await client.get(f"{H}/articles/{slug}", params=public)).json()["title"] == "Testing the help desk, again"
    found = (await client.get(f"{H}/search", params={**public, "q": "help desk again"})).json()["results"]
    assert slug in [x["slug"] for x in found]
    r = await client.post(f"{OPS}/{aid}/unpublish", headers=cm_in)
    assert r.json()["status"] == "draft"
    assert (await client.get(f"{H}/articles/{slug}", params=public)).status_code == 404
    assert (await client.post(f"{OPS}/{aid}/unpublish", headers=cm_in)).status_code == 409

    history = (await client.get(f"{OPS}/{aid}/history", headers=support)).json()
    assert [h["action"] for h in history] == ["unpublished", "published", "edited", "published", "created"]
    assert history[0]["by_name"] == "India Country Manager"

    from sqlalchemy import select

    from core_api.modules.audit.models import AuditLog
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(AuditLog).where(AuditLog.entity_id == aid).order_by(AuditLog.at))).scalars().all()
    assert [a.action for a in rows] == ["help.created", "help.published", "help.edited", "help.published", "help.unpublished"]
    assert all(a.scope == "IN" and a.actor_id for a in rows)

    # The super admin writes global help
    root = await login(client, "admin@example.com", PW)
    r = await client.post(OPS, headers=root, json={**body, "country": "*", "slug": f"{slug}-global"})
    assert r.status_code == 201 and r.json()["can_edit"]
    assert (await client.patch(f"{OPS}/{r.json()['id']}", headers=cm_in, json={"title": "Not mine"})).status_code == 403


async def test_votes_are_anonymous_changeable_and_rate_limited(client: AsyncClient) -> None:  # noqa: F811
    a = (await client.get(f"{H}/articles/delivery-pin", params={"country": "IN", "language": "en"})).json()
    voter = uuid.uuid4().hex
    assert (await client.post(f"{H}/votes", json={"article_id": a["id"], "helpful": True, "voter": voter})).status_code == 202
    assert (await client.post(f"{H}/votes", json={"article_id": a["id"], "helpful": False, "voter": voter})).status_code == 202
    root = await login(client, "admin@example.com", PW)
    row = (await client.get(f"{OPS}/{a['id']}", headers=root)).json()
    assert row["helpful_no"] >= 1
    assert (await client.post(f"{H}/votes", json={"article_id": str(uuid.uuid4()), "helpful": True})).status_code == 404
    codes = [(await client.post(f"{H}/votes", json={"article_id": a["id"], "helpful": True, "voter": uuid.uuid4().hex})).status_code
             for _ in range(12)]
    assert 429 in codes


async def test_contact_form_creates_a_ticket_and_is_spam_safe(client: AsyncClient) -> None:  # noqa: F811
    note = f"My order never came, ref {uuid.uuid4().hex[:6]}"
    form = {"name": "Asha Rao", "email": "asha@example.com", "topic": "orders", "message": note, "country": "IN",
            "city": "IN-TG-HYD", "language": "en"}
    r = await client.post(f"{H}/contact", json=form)
    assert r.status_code == 201 and r.json() == {"ok": True}
    # A bot fills in the hidden field: thanked, dropped
    assert (await client.post(f"{H}/contact", json={**form, "website": "http://spam", "message": "spam " + note})).status_code == 201
    assert (await client.post(f"{H}/contact", json={**form, "email": "not-an-email"})).status_code == 422
    codes = [(await client.post(f"{H}/contact", json=form)).status_code for _ in range(3)]
    assert 429 in codes

    support = await login(client, "support.hyd@example.com", PW)
    tickets = (await client.get("/api/v1/ops/tickets", headers=support, params={"scope": "IN-TG-HYD"})).json()
    mine = [t for t in tickets if t["kind"] == "contact" and t["note"] == note]
    assert mine and mine[0]["requester_name"] == "Asha Rao" and mine[0]["details"]["email"] == "asha@example.com"
    assert not [t for t in tickets if t["note"] == "spam " + note]


async def test_signed_in_customer_messages_support_about_an_order(client: AsyncClient) -> None:  # noqa: F811
    h = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, h)
    r = await client.post(f"{H}/messages", headers=h, json={"topic": "orders", "message": "Please call me about this order",
                                                            "order_id": order["id"]})
    assert r.status_code == 201, r.text
    other = await login(client, "customer2.hyd@example.com")
    assert (await client.post(f"{H}/messages", headers=other, json={"topic": "orders", "message": "Not my order at all",
                                                                    "order_id": order["id"]})).status_code == 404
    assert (await client.post(f"{H}/messages", json={"topic": "orders", "message": "No token here"})).status_code in (401, 403)
    ops = await login(client, "ops.hyd@example.com", PW)
    tickets = (await client.get("/api/v1/ops/tickets", headers=ops, params={"scope": "IN-TG-HYD"})).json()
    assert any(t["id"] == r.json()["id"] and t["kind"] == "message" and t["order_id"] == order["id"] for t in tickets)
