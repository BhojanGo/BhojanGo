"""P15 on the migrated database: a real order through core_api, its outbox
events through the worker. Telugu for a customer who chose it, push with dead
tokens forgotten, email receipt, SMS to a restaurant with no app, each
message once even when the event comes twice."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


class RecordingPush:
    name = "recording"

    def __init__(self, dead: set[str]) -> None:
        self.dead, self.sent = dead, []

    async def send(self, devices, message):  # type: ignore[no-untyped-def]
        from shared.providers.push import PushResult

        self.sent.append((sorted(d.token for d in devices), message))
        return PushResult(sent=sum(d.token not in self.dead for d in devices),
                          invalid=[d.token for d in devices if d.token in self.dead])


class RecordingEmail:
    name = "recording"

    def __init__(self) -> None:
        self.sent = []

    async def send(self, to, subject, html, text=""):  # type: ignore[no-untyped-def]
        self.sent.append((to, subject, html, text))
        return True


async def events_for(order_id: str, kind: str) -> list[dict]:
    from shared.db import AsyncSessionLocal
    from shared.outbox import OutboxEvent

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == order_id,
                                                           OutboxEvent.event_type == kind)
                                 .order_by(OutboxEvent.created_at))).scalars().all()
        return [r.envelope for r in rows]


async def run(event: dict, push: RecordingPush, email: RecordingEmail) -> list[dict]:
    from app.services.dispatcher import Sender, dispatch_event
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        out = await dispatch_event(event, db, Sender(db, push=push, email=email))  # type: ignore[arg-type]
        await db.commit()
        return out


async def test_order_messages_in_telugu_once(capsys) -> None:  # type: ignore[no-untyped-def]
    from app.models.notification import DeviceToken, Notification
    from core_api.integration.test_orders_flow import login, move, new_order, pay, user_id
    from core_api.main import app
    from shared.db import AsyncSessionLocal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cust = await login(client, "customer5.hyd@example.com")
        r = await client.patch("/api/v1/users/me", headers=cust, json={"preferred_locale": "te-IN"})
        assert r.status_code == 200, r.text
        live, dead = f"ExponentPushToken[{uuid.uuid4().hex[:20]}]", f"ExponentPushToken[{uuid.uuid4().hex[:20]}]"
        async with AsyncSessionLocal() as db:
            await db.execute(DeviceToken.__table__.delete().where(DeviceToken.user_id == uuid.UUID(user_id(cust))))
            db.add_all([DeviceToken(user_id=uuid.UUID(user_id(cust)), token=t, platform="ios", provider="expo")
                        for t in (live, dead)])
            await db.commit()
        try:
            order = await new_order(client, cust)
            await pay(client, cust, order)
            push, email = RecordingPush({dead}), RecordingEmail()

            [placed] = await events_for(order["id"], "order.placed")
            results = await run(placed, push, email)
            assert results == [{"in_app": "sent", "push": "sent", "email": "sent"},  # customer
                               {"in_app": "sent", "sms": "sent"}]                     # restaurant: no app → SMS
            tokens, msg = push.sent[0]
            assert tokens == sorted([live, dead])
            assert msg.title == "ఆర్డర్ అందింది" and "Spice Route Kitchen" in msg.body
            to, subject, html, _ = email.sent[0]
            assert to == "customer5.hyd@example.com" and "ఆర్డర్ అందింది" in subject and 'lang="te"' in html
            assert "₹" in html
            sms = capsys.readouterr().out
            assert "BhojanGo: 2 items, ₹" in sms and "Accept by" in sms  # the partner reads English

            async with AsyncSessionLocal() as db:
                left = (await db.execute(select(DeviceToken.token).where(
                    DeviceToken.user_id == uuid.UUID(user_id(cust))))).scalars().all()
                assert left == [live]  # the dead token is forgotten
                rows = (await db.execute(select(Notification.channel, Notification.status, Notification.language)
                                         .where(Notification.event_id == placed["event_id"]))).all()
                assert sorted(rows) == sorted([("in_app", "sent", "te"), ("push", "sent", "te"), ("email", "sent", "te"),
                                               ("in_app", "sent", "en"), ("sms", "sent", "en")])

            # The queue delivers it again: nothing is sent twice.
            assert await run(placed, push, email) == [{}, {}]
            assert len(push.sent) == 1 and len(email.sent) == 1

            partner = await login(client, "partner.hyd@example.com")
            assert (await move(client, partner, order["id"], "accepted")).status_code == 200
            [accepted] = await events_for(order["id"], "order.status_changed")
            await run(accepted, push, email)
            _, msg = push.sent[-1]
            assert msg.title == "ఆర్డర్ అంగీకరించారు" and "సుమారు" in msg.body and "కి చేరుతుంది." in msg.body
            assert accepted["payload"]["estimated_delivery_time"]
        finally:
            await client.patch("/api/v1/users/me", headers=cust, json={"preferred_locale": "en-IN"})
            async with AsyncSessionLocal() as db:
                await db.execute(DeviceToken.__table__.delete().where(DeviceToken.user_id == uuid.UUID(user_id(cust))))
                await db.commit()
