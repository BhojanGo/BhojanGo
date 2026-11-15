"""The web's account area on SQLite: addresses (default, notes, edit), saved
cards (never a card number), notification preferences, locales, and what
account deletion removes. Favourites, order history, reorder, receipts and the
export need the catalog and orders tables: core_api/integration/test_account.py."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core_api.modules.identity.models.account import Favourite, NotificationPreference
from core_api.modules.identity.models.address import Address
from core_api.modules.identity.tests.test_p5_auth import bearer, login, make_user
from core_api.modules.payments.models.payment_method import PaymentMethod

NEXT_YEAR = datetime.now(UTC).year + 1


async def signed_in(client: AsyncClient, db_session) -> tuple[dict, uuid.UUID]:  # type: ignore[no-untyped-def]
    email = f"acct-{uuid.uuid4().hex[:8]}@example.com"
    user = await make_user(db_session, email)
    return bearer(await login(client, email)), user.id


def card(**kw) -> dict:  # type: ignore[no-untyped-def]
    return {"provider": "fake", "provider_token": f"pm_fake_{uuid.uuid4().hex[:10]}", "brand": "Visa", "last4": "4242",
            "exp_month": 12, "exp_year": NEXT_YEAR, **kw}


# ── addresses ────────────────────────────────────────────────────────────────

async def add(client: AsyncClient, h: dict, street: str, **kw) -> dict:  # type: ignore[no-untyped-def]
    r = await client.post("/api/v1/me/addresses", headers=h, json={"street": street, "city": "Hyderabad", **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def defaults(client: AsyncClient, h: dict) -> list[str]:
    return [a["street"] for a in (await client.get("/api/v1/me/addresses", headers=h)).json() if a["is_default"]]


async def test_the_first_address_is_the_default_and_there_is_only_ever_one(client: AsyncClient, db_session) -> None:
    h, _ = await signed_in(client, db_session)
    home = await add(client, h, "Flat 1", delivery_notes="Ring twice")
    assert home["is_default"] and home["delivery_notes"] == "Ring twice"
    work = await add(client, h, "Office 9")
    assert not work["is_default"]
    assert await defaults(client, h) == ["Flat 1"]

    r = await client.post(f"/api/v1/me/addresses/{work['id']}/default", headers=h)
    assert r.status_code == 200 and r.json()["is_default"]
    assert await defaults(client, h) == ["Office 9"]

    gym = await add(client, h, "Gym", is_default=True)  # asked for: takes over
    assert gym["is_default"] and await defaults(client, h) == ["Gym"]


async def test_patch_changes_only_what_is_sent(client: AsyncClient, db_session) -> None:
    h, _ = await signed_in(client, db_session)
    a = await add(client, h, "Flat 1", lat=17.44, lng=78.39, postal_code="500081")
    r = await client.patch(f"/api/v1/me/addresses/{a['id']}", headers=h,
                           json={"label": "Mum's", "delivery_notes": "Gate code 4512", "lat": None, "lng": None})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["label"], out["delivery_notes"], out["lat"], out["street"], out["postal_code"]) == (
        "Mum's", "Gate code 4512", None, "Flat 1", "500081")

    assert (await client.patch(f"/api/v1/me/addresses/{a['id']}", headers=h, json={"street": None})).status_code == 422
    assert (await client.patch(f"/api/v1/me/addresses/{a['id']}", headers=h,
                               json={"delivery_notes": "x" * 501})).status_code == 422
    # The only default can't just be switched off: another address has to take over.
    r = await client.patch(f"/api/v1/me/addresses/{a['id']}", headers=h, json={"is_default": False})
    assert r.status_code == 422
    b = await add(client, h, "Office 9")
    r = await client.patch(f"/api/v1/me/addresses/{b['id']}", headers=h, json={"is_default": True})
    assert r.json()["is_default"] and await defaults(client, h) == ["Office 9"]


async def test_deleting_the_default_promotes_the_newest_remaining(client: AsyncClient, db_session) -> None:
    h, uid = await signed_in(client, db_session)
    first = await add(client, h, "Oldest")
    await add(client, h, "Middle")
    await add(client, h, "Newest")
    # SQLite's now() is to the second: make the order of creation unambiguous.
    rows = (await db_session.execute(select(Address).where(Address.user_id == uid))).scalars().all()
    base = datetime(2026, 1, 1)
    for r in rows:
        r.created_at = base + timedelta(minutes={"Oldest": 0, "Middle": 1, "Newest": 2}[r.street])
    await db_session.flush()

    assert (await client.delete(f"/api/v1/me/addresses/{first['id']}", headers=h)).status_code == 204
    assert await defaults(client, h) == ["Newest"]


async def test_someone_elses_address_is_not_found(client: AsyncClient, db_session) -> None:
    h, _ = await signed_in(client, db_session)
    other, _ = await signed_in(client, db_session)
    a = await add(client, h, "Flat 1")
    assert (await client.patch(f"/api/v1/me/addresses/{a['id']}", headers=other, json={"label": "x"})).status_code == 404
    assert (await client.post(f"/api/v1/me/addresses/{a['id']}/default", headers=other)).status_code == 404


# ── saved cards ──────────────────────────────────────────────────────────────

async def test_cards_are_saved_as_tokens_and_the_token_never_comes_back(client: AsyncClient, db_session) -> None:
    h, uid = await signed_in(client, db_session)
    first = card()
    r = await client.post("/api/v1/me/payment-methods", headers=h, json=first)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["is_default"] and out["brand"] == "visa" and out["last4"] == "4242"
    assert "provider_token" not in out and first["provider_token"] not in r.text

    second = (await client.post("/api/v1/me/payment-methods", headers=h,
                                json=card(provider="stripe", provider_token="pm_1QaBcDeFgHiJkLmN", last4="0005"))).json()
    assert not second["is_default"]
    listed = (await client.get("/api/v1/me/payment-methods", headers=h))
    assert {m["last4"] for m in listed.json()} == {"4242", "0005"} and "pm_" not in listed.text

    async def default_ids() -> set[str]:
        return {m["id"] for m in (await client.get("/api/v1/me/payment-methods", headers=h)).json() if m["is_default"]}

    r = await client.post(f"/api/v1/me/payment-methods/{second['id']}/default", headers=h)
    assert r.json()["is_default"]
    assert await default_ids() == {second["id"]}

    # The default goes: the remaining card takes over.
    assert (await client.delete(f"/api/v1/me/payment-methods/{second['id']}", headers=h)).status_code == 204
    assert await default_ids() == {out["id"]}

    assert (await client.post("/api/v1/me/payment-methods", headers=h, json=first)).status_code == 409  # same token
    stored = (await db_session.execute(select(PaymentMethod).where(PaymentMethod.user_id == uid))).scalars().all()
    assert [m.provider_token for m in stored] == [first["provider_token"]]


@pytest.mark.parametrize("body", [
    card(provider_token="4242424242424242"),
    card(provider_token="pm_4242424242424242"),
    card(brand="4242 4242 4242 4242"),
    card(card_number="4242-4242-4242-4242"),
    card(number=4242424242424242),
    card(meta={"pan": "5555 5555 5555 4444"}),
    card(last4="4242", note="378282246310005"),  # Amex, 15 digits
], ids=["token", "inside-token", "spaces", "dashes-extra-field", "a-number", "nested", "amex"])
async def test_anything_that_looks_like_a_card_number_is_refused(client: AsyncClient, db_session, body: dict) -> None:
    h, uid = await signed_in(client, db_session)
    r = await client.post("/api/v1/me/payment-methods", headers=h, json=body)
    assert r.status_code == 422, r.text
    assert "card number" in r.text
    assert (await db_session.execute(select(PaymentMethod).where(PaymentMethod.user_id == uid))).first() is None


@pytest.mark.parametrize("body", [
    card(provider="stripe", provider_token="tok_visa"),          # not a payment method token
    card(provider="razorpay", provider_token="pm_abc123"),
    card(provider="fake", provider_token="pm_abc123"),
    card(last4="42"),
    card(last4="42a4"),
    card(exp_month=13),
    card(exp_month=1, exp_year=datetime.now(UTC).year - 1),     # expired
    card(provider="paypal"),
])
async def test_bad_cards_are_refused(client: AsyncClient, db_session, body: dict) -> None:
    h, _ = await signed_in(client, db_session)
    assert (await client.post("/api/v1/me/payment-methods", headers=h, json=body)).status_code == 422


async def test_someone_elses_card_is_not_found(client: AsyncClient, db_session) -> None:
    h, _ = await signed_in(client, db_session)
    other, _ = await signed_in(client, db_session)
    m = (await client.post("/api/v1/me/payment-methods", headers=h, json=card())).json()
    assert (await client.delete(f"/api/v1/me/payment-methods/{m['id']}", headers=other)).status_code == 404
    assert (await client.post(f"/api/v1/me/payment-methods/{m['id']}/default", headers=other)).status_code == 404
    assert len((await client.get("/api/v1/me/payment-methods", headers=h)).json()) == 1


# ── notification preferences ─────────────────────────────────────────────────

async def test_offers_are_off_until_turned_on(client: AsyncClient, db_session) -> None:
    h, _ = await signed_in(client, db_session)
    prefs = (await client.get("/api/v1/me/notification-preferences", headers=h)).json()
    assert prefs == {"orders": {"push": True, "sms": True, "email": True},
                     "offers": {"push": False, "sms": False, "email": False},
                     "account": {"push": True, "sms": True, "email": True}}

    r = await client.put("/api/v1/me/notification-preferences", headers=h,
                         json={"offers": {"email": True}, "orders": {"sms": False}})
    assert r.status_code == 200, r.text
    assert r.json()["offers"] == {"push": False, "sms": False, "email": True}
    assert r.json()["orders"] == {"push": True, "sms": False, "email": True}
    # Only what was sent changes; it's kept.
    r = await client.put("/api/v1/me/notification-preferences", headers=h, json={"offers": {"push": True}})
    again = (await client.get("/api/v1/me/notification-preferences", headers=h)).json()
    assert again == r.json() and again["offers"] == {"push": True, "sms": False, "email": True}
    assert again["orders"]["sms"] is False
    assert (await client.put("/api/v1/me/notification-preferences", headers=h,
                             json={"offers": {"push": "maybe"}})).status_code == 422


# ── locales ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("locale", ["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN", "bn-IN", "en-US", "es-US"])
async def test_the_web_languages_are_accepted(client: AsyncClient, db_session, locale: str) -> None:
    h, _ = await signed_in(client, db_session)
    r = await client.patch("/api/v1/users/me", headers=h, json={"preferred_locale": locale})
    assert r.status_code == 200 and r.json()["preferred_locale"] == locale


async def test_other_locales_are_refused(client: AsyncClient, db_session) -> None:
    h, _ = await signed_in(client, db_session)
    assert (await client.patch("/api/v1/users/me", headers=h, json={"preferred_locale": "fr-FR"})).status_code == 422


# ── account deletion ─────────────────────────────────────────────────────────

async def test_deleting_the_account_removes_cards_favourites_and_preferences(client: AsyncClient, db_session) -> None:
    from core_api.modules.catalog.service import lookup as catalog_lookup
    from core_api.modules.orders.service import lookup as order_lookup

    h, uid = await signed_in(client, db_session)
    await client.post("/api/v1/me/payment-methods", headers=h, json=card())
    await client.put("/api/v1/me/notification-preferences", headers=h, json={"offers": {"email": True}})
    db_session.add(Favourite(user_id=uid, kind="restaurant", target_id=uuid.uuid4()))
    await db_session.flush()

    r = await client.delete("/api/v1/users/me", headers=h)
    assert r.status_code == 200, r.text
    for model in (PaymentMethod, Favourite, NotificationPreference):
        assert (await db_session.execute(select(model).where(model.user_id == uid))).first() is None, model.__name__
    # Orders and reviews are kept but anonymised (checked on Postgres in the integration tests).
    order_lookup.forget_customer.assert_awaited_with(db_session, uid)  # type: ignore[attr-defined]
    catalog_lookup.forget_reviewer.assert_awaited_with(db_session, uid)  # type: ignore[attr-defined]
