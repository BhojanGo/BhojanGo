"""The fake gateway and webhook handling: outcomes, signatures, idempotency.

Payment initiation needs a real order (amount from the order), so it is
tested on Postgres in core_api/integration/test_orders_flow.py.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core_api.main import app
from core_api.modules.payments.models.payment import PaymentIntent, ProcessedWebhookEvent, Wallet, WalletTransaction
from core_api.modules.payments.service import gateways
from shared.config import get_settings
from shared.db import Base, get_db
from shared.outbox import OutboxEvent
from shared.providers import ProviderConfigError

TABLES = [PaymentIntent.__table__, Wallet.__table__, WalletTransaction.__table__, ProcessedWebhookEvent.__table__]
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
def hooks():
    """The outbox and the orders hook, recorded instead of touching their tables."""
    with (
        patch("shared.outbox.add", new_callable=AsyncMock) as add,
        patch("core_api.modules.orders.service.order.OrderService.on_payment_succeeded", new_callable=AsyncMock) as placed,
        patch("core_api.modules.orders.service.order.OrderService.on_payment_failed", new_callable=AsyncMock),
        patch("core_api.modules.payments.api.v1.payments._record_tax_transaction", new_callable=AsyncMock),
    ):
        yield add, placed


async def make_intent(pm: str | None = None) -> PaymentIntent:
    created = await gateways.FakeGateway("IN").create(amount=63822, currency="INR", order_id="o",
                                                      idempotency_key=str(uuid.uuid4()), payment_method_id=pm)
    async with Session() as s:
        intent = PaymentIntent(order_id=uuid.uuid4(), user_id=uuid.uuid4(), provider="fake",
                               provider_payment_id=created["provider_payment_id"], amount=63822, currency="INR",
                               status="pending", idempotency_key=str(uuid.uuid4()), metadata_={"fake_outcome": created["fake_outcome"]})
        s.add(intent)
        await s.commit()
        return intent


async def deliver(client: AsyncClient, pid: str, outcome: str, body: bytes | None = None):  # type: ignore[no-untyped-def]
    body = body or gateways.fake_webhook_body(pid, outcome)
    return await client.post("/api/v1/payments/fake/webhook", content=body, headers={"x-fake-signature": gateways.sign_fake(body)})


async def test_success_places_the_order_once(client, hooks) -> None:
    add, placed = hooks
    intent = await make_intent("pm_card_visa")
    body = gateways.fake_webhook_body(intent.provider_payment_id, "succeeded")
    r = await deliver(client, intent.provider_payment_id, "succeeded", body)
    assert r.json() == {"received": True}
    assert placed.await_count == 1 and placed.await_args.args[0] == intent.order_id
    assert add.await_args.args[1] == "payment.succeeded"

    # The same event again (gateways retry): ignored by event id.
    r = await deliver(client, intent.provider_payment_id, "succeeded", body)
    assert r.json()["duplicate"] is True
    # A different event with the same outcome: ignored by status.
    r = await deliver(client, intent.provider_payment_id, "succeeded")
    assert r.json()["duplicate"] is True
    # A late failure never undoes a captured payment.
    r = await deliver(client, intent.provider_payment_id, "failed")
    assert r.json()["duplicate"] is True
    assert placed.await_count == 1
    async with Session() as s:
        assert (await s.get(PaymentIntent, intent.id)).status == "succeeded"


async def test_failure_is_recorded_and_does_not_place(client, hooks) -> None:
    add, placed = hooks
    intent = await make_intent("pm_card_chargeDeclined")
    await deliver(client, intent.provider_payment_id, "failed")
    assert placed.await_count == 0 and add.await_args.args[1] == "payment.failed"


async def test_bad_signature_is_rejected(client) -> None:
    body = gateways.fake_webhook_body("fake_pay_x", "succeeded")
    r = await client.post("/api/v1/payments/fake/webhook", content=body, headers={"x-fake-signature": "nope"})
    assert r.status_code == 400


def test_outcomes_follow_stripe_test_cards() -> None:
    assert gateways.fake_outcome("pm_card_visa") == "succeeded"
    assert gateways.fake_outcome("pm_card_chargeDeclined") == "failed"
    assert gateways.fake_outcome(None) == "succeeded"


def test_fake_gateway_is_refused_in_production(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(ProviderConfigError):
        gateways.get_gateway("US")
    monkeypatch.setattr(get_settings().providers, "PAYMENT_PROVIDER", "fake")
    with pytest.raises(ProviderConfigError):
        gateways.get_gateway("IN")


def test_outbox_model_is_importable() -> None:
    assert OutboxEvent.__tablename__ == "outbox_events"
