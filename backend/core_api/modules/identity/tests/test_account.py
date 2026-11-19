"""The web's account area on SQLite: addresses (default, notes, edit), saved
cards (never a card number), notification preferences, locales, and what
account deletion removes. Favourites, order history, reorder, receipts and the
export need the catalog and orders tables: core_api/integration/test_account.py."""
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core_api.modules.identity.models.account import Favourite, NotificationPreference
from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.rider import RiderProfile
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
                                json=card(provider="stripe", provider_token="pm_test_second_card", last4="0005"))).json()
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
    db_session.add(RiderProfile(user_id=uid, date_of_birth=date(1990, 1, 1), vehicle="scooter"))  # a delivery partner's (R9)
    await db_session.flush()

    r = await client.delete("/api/v1/users/me", headers=h)
    assert r.status_code == 200, r.text
    for model in (PaymentMethod, Favourite, NotificationPreference, RiderProfile):
        assert (await db_session.execute(select(model).where(model.user_id == uid))).first() is None, model.__name__
    # Orders and reviews are kept but anonymised (checked on Postgres in the integration tests).
    order_lookup.forget_customer.assert_awaited_with(db_session, uid)  # type: ignore[attr-defined]
    catalog_lookup.forget_reviewer.assert_awaited_with(db_session, uid)  # type: ignore[attr-defined]


# ── account deletion by delivery partners and kitchen owners (R19) ──────────

async def signed_in_as(client: AsyncClient, db_session, role: str, country: str = "US") -> tuple[dict, uuid.UUID]:  # type: ignore[no-untyped-def]
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    user = await make_user(db_session, email, country=country, role=role)
    return bearer(await login(client, email)), user.id


async def test_a_delivery_partners_documents_and_their_photos_go_with_the_account(client: AsyncClient, db_session, tmp_path) -> None:
    from unittest.mock import patch

    from core_api.modules.identity.models.rider import RiderDocument
    from shared.providers.storage import LocalStorage

    h, uid = await signed_in_as(client, db_session, "driver")
    storage = LocalStorage(str(tmp_path))
    keys = [f"rider_document/{uid}/{uuid.uuid4().hex}.jpg" for _ in range(2)]
    for key, kind in zip(keys, ("licence", "insurance"), strict=True):
        await storage.put(key, b"photo", "image/jpeg")
        db_session.add(RiderDocument(rider_id=uid, kind=kind, status="approved", file_key=key))
    db_session.add(RiderDocument(rider_id=uid, kind="background", status="submitted"))  # no file
    other = await make_user(db_session, f"other-{uuid.uuid4().hex[:6]}@example.com", role="driver")
    db_session.add(RiderDocument(rider_id=other.id, kind="licence", status="approved", file_key=f"rider_document/{other.id}/x.jpg"))
    await db_session.flush()

    with patch("shared.providers.storage.get_storage", lambda: storage):
        r = await client.delete("/api/v1/users/me", headers=h)
    assert r.status_code == 200, r.text
    left = (await db_session.execute(select(RiderDocument.rider_id).where(RiderDocument.rider_id.in_([uid, other.id])))).scalars().all()
    assert left == [other.id]  # only someone else's
    assert not any([await storage.exists(k) for k in keys])


async def test_a_photo_the_storage_cant_remove_does_not_stop_the_deletion(client: AsyncClient, db_session) -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from core_api.modules.identity.models.rider import RiderDocument

    h, uid = await signed_in_as(client, db_session, "driver")
    db_session.add(RiderDocument(rider_id=uid, kind="licence", status="approved", file_key=f"rider_document/{uid}/a.jpg"))
    await db_session.flush()
    broken = MagicMock(delete=AsyncMock(side_effect=OSError("bucket unreachable")))
    with patch("shared.providers.storage.get_storage", lambda: broken):
        assert (await client.delete("/api/v1/users/me", headers=h)).status_code == 200
    assert (await db_session.execute(select(RiderDocument).where(RiderDocument.rider_id == uid))).first() is None


async def test_deletion_waits_while_a_payout_is_owed(client: AsyncClient, db_session) -> None:
    from unittest.mock import AsyncMock, patch

    from core_api.modules.identity.models.user import User

    h, uid = await signed_in_as(client, db_session, "driver")
    owed = AsyncMock(return_value={"USD": 1250})
    with patch("core_api.modules.finance.service.lookup.money_owed", owed):
        r = await client.delete("/api/v1/users/me", headers=h)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "MONEY_OWED" and detail["currency"] == "USD" and "12.50" in detail["amount"]
    assert owed.await_args.kwargs == {"rider_id": uid, "restaurant_ids": []}
    user = await db_session.get(User, uid)
    assert user.is_active and user.email  # nothing was removed
    assert (await client.get("/api/v1/users/me", headers=h)).status_code == 200  # still signed in


async def test_deletion_waits_for_orders_in_progress(client: AsyncClient, db_session) -> None:
    from unittest.mock import AsyncMock, patch

    h, _ = await signed_in_as(client, db_session, "driver")
    with patch("core_api.modules.orders.service.lookup.orders_in_progress", AsyncMock(return_value=1)):
        r = await client.delete("/api/v1/users/me", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ORDERS_IN_PROGRESS"


async def test_a_kitchen_owners_kitchens_close_when_the_account_goes(client: AsyncClient, db_session) -> None:
    from unittest.mock import AsyncMock, patch

    h, uid = await signed_in_as(client, db_session, "restaurant_owner")
    kitchen = uuid.uuid4()
    close = AsyncMock(return_value=1)
    owed = AsyncMock(return_value={})
    with (patch("core_api.modules.catalog.service.lookup.owned_restaurant_ids", AsyncMock(return_value=[kitchen])),
          patch("core_api.modules.finance.service.lookup.money_owed", owed),
          patch("core_api.modules.catalog.service.lookup.close_for_departed_owner", close)):
        assert (await client.delete("/api/v1/users/me", headers=h)).status_code == 200
    assert owed.await_args.kwargs == {"rider_id": None, "restaurant_ids": [kitchen]}
    close.assert_awaited_once()
    assert close.await_args.args[1] == uid


async def test_customers_have_nothing_to_wait_for(client: AsyncClient, db_session) -> None:
    from unittest.mock import AsyncMock, patch

    h, _ = await signed_in_as(client, db_session, "customer")
    owed = AsyncMock(return_value={"USD": 100})
    with patch("core_api.modules.finance.service.lookup.money_owed", owed):
        assert (await client.delete("/api/v1/users/me", headers=h)).status_code == 200
    owed.assert_not_awaited()
