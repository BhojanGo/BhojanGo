"""The fake payment gateway: create, webhook outcomes, idempotency, refunds."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core_api.main import app
from core_api.modules.identity.service.security import create_access_token
from core_api.modules.payments.models.payment import PaymentIntent, Wallet, WalletTransaction
from core_api.modules.payments.service import gateways
from shared.config import get_settings
from shared.db import Base, get_db
from shared.providers import ProviderConfigError

TABLES = [PaymentIntent.__table__, Wallet.__table__, WalletTransaction.__table__]
engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=TABLES)

    async def override():
        async with Session() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_db] = override
    yield
    app.dependency_overrides.pop(get_db, None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=TABLES)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def auth(user_id: str) -> dict:
    token, _ = create_access_token(user_id, "c@example.com", "customer", "US")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def published():
    with patch("core_api.modules.payments.api.v1.payments.publish_payment_event", new_callable=AsyncMock) as m:
        yield m


async def _initiate(client: AsyncClient, auth: dict, pm: str | None = None, country: str = "US") -> dict:
    body = {
        "order_id": str(uuid.uuid4()),
        "payment_method_type": "card",
        "payment_method_id": pm,
        "country": country,
        "amount": 2599,
        "currency": "USD" if country == "US" else "INR",
    }
    r = await client.post("/api/v1/payments/initiate", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


async def test_initiate_uses_fake_gateway_without_keys(client, auth) -> None:
    data = await _initiate(client, auth)
    assert data["provider"] == "fake"
    assert data["client_secret"].startswith("fake_pay_")

    india = await _initiate(client, auth, country="IN")
    assert india["razorpay_order_id"].startswith("fake_pay_")


async def test_complete_succeeds_once_and_duplicate_webhook_is_ignored(client, auth, published) -> None:
    data = await _initiate(client, auth, pm="pm_card_visa")
    r = await client.post(f"/api/v1/payments/fake/{data['payment_intent_id']}/complete", json={}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "succeeded"
    assert published.await_count == 1
    assert published.await_args.args[0] == "payment.succeeded"

    async with Session() as s:
        intent = await s.get(PaymentIntent, uuid.UUID(data["payment_intent_id"]))
        assert intent.status == "succeeded"
        pid = intent.provider_payment_id

    # The same webhook delivered again (gateways retry) changes nothing.
    body = gateways.fake_webhook_body(pid, "succeeded")
    r = await client.post("/api/v1/payments/fake/webhook", content=body,
                          headers={"x-fake-signature": gateways.sign_fake(body)})
    assert r.json() == {"received": True, "duplicate": True}
    # A late failure never undoes a captured payment.
    body = gateways.fake_webhook_body(pid, "failed")
    r = await client.post("/api/v1/payments/fake/webhook", content=body,
                          headers={"x-fake-signature": gateways.sign_fake(body)})
    assert r.json()["duplicate"] is True
    assert published.await_count == 1


async def test_declined_test_card_fails(client, auth, published) -> None:
    data = await _initiate(client, auth, pm="pm_card_chargeDeclined")
    r = await client.post(f"/api/v1/payments/fake/{data['payment_intent_id']}/complete", json={}, headers=auth)
    assert r.json()["outcome"] == "failed"
    assert published.await_args.args[0] == "payment.failed"


async def test_bad_signature_is_rejected(client) -> None:
    body = gateways.fake_webhook_body("fake_pay_x", "succeeded")
    r = await client.post("/api/v1/payments/fake/webhook", content=body, headers={"x-fake-signature": "nope"})
    assert r.status_code == 400


async def test_only_the_payer_can_complete(client, auth) -> None:
    data = await _initiate(client, auth)
    token, _ = create_access_token(str(uuid.uuid4()), "x@example.com", "customer", "US")
    r = await client.post(f"/api/v1/payments/fake/{data['payment_intent_id']}/complete", json={},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


async def test_partial_refund_through_fake_gateway(client, auth, published) -> None:
    data = await _initiate(client, auth)
    await client.post(f"/api/v1/payments/fake/{data['payment_intent_id']}/complete", json={}, headers=auth)
    async with Session() as s:
        order_id = (await s.get(PaymentIntent, uuid.UUID(data["payment_intent_id"]))).order_id
    r = await client.post(f"/api/v1/payments/{order_id}/refund",
                          json={"amount": 599, "reason": "missing item", "refund_to": "original_payment"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["refund_id"].startswith("fake_re_")
    async with Session() as s:
        intent = await s.get(PaymentIntent, uuid.UUID(data["payment_intent_id"]))
        assert (intent.status, intent.refunded_amount) == ("partially_refunded", 599)


def test_fake_gateway_is_refused_in_production(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(ProviderConfigError):
        gateways.get_gateway("US")
    monkeypatch.setattr(get_settings().providers, "PAYMENT_PROVIDER", "fake")
    with pytest.raises(ProviderConfigError):
        gateways.get_gateway("IN")
