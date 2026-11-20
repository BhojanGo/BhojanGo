"""R20: app store review orders on Postgres. In the hidden review city
(tools/review_accounts.py), the review customer's order shows the usual bill, costs
$0.00 and is placed at once with no payment provider (nor tax provider) called; the
review simulator's signed step endpoint moves only such orders.

And the other way round: a normal customer in a normal city still pays, the review
customer pays outside the review city, a normal customer can't order in the review
city, and the step endpoint refuses (404) every order that isn't a review order.

The worker's review simulator driving the order to delivered:
worker/tests/integration/test_review_sim_db.py.
"""
import json
import os
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_review_accounts import bearer, command, remove

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

CODE = "US-ID-REV"


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from httpx import ASGITransport

    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


class ProviderCalled(AssertionError):
    pass


def no_providers(monkeypatch) -> list[str]:  # type: ignore[no-untyped-def]
    """Every way to reach a payment provider (or Stripe Tax) raises and is recorded."""
    from core_api.modules.payments.api.v1 import payments
    from core_api.modules.payments.service import order_payments, refunds
    from core_api.modules.pricing.service import quotes

    calls: list[str] = []

    def refuse(name: str):  # type: ignore[no-untyped-def]
        def f(*a, **k):  # type: ignore[no-untyped-def]
            calls.append(name)
            raise ProviderCalled(f"{name} was called")
        return f

    for mod, name in ((payments, "get_gateway"), (payments, "gateway_by_name"), (order_payments, "gateway_by_name"),
                      (refunds, "gateway_by_name"), (quotes, "get_tax_provider")):
        monkeypatch.setattr(mod, name, refuse(name))
    return calls


async def make_review_city():  # type: ignore[no-untyped-def]
    """Run the command (as at go-live); returns (module, args, logins by app, emails)."""
    from shared.db import AsyncSessionLocal

    cmd = command()
    args = cmd.parse_args(["--email-domain", f"r{uuid.uuid4().hex[:8]}.example.com"])
    emails = list(cmd.emails(args.email_domain).values())
    await remove(CODE, emails)  # a run that stopped half way
    async with AsyncSessionLocal() as db:
        logins = {row.who: row for row in await cmd.create(db, args)}
        await db.commit()
    return cmd, logins, emails


async def review_kitchen(client: AsyncClient, cmd, h: dict) -> dict:  # type: ignore[no-untyped-def]
    lat, lng = cmd.CENTRES["US"]
    return next(k for k in (await client.get("/api/v1/discover", params={"lat": lat + 0.01, "lng": lng}, headers=h)).json()
                ["restaurants"] if k["name"] == cmd.KITCHEN_NAME)


async def quote_and_order(client: AsyncClient, cmd, h: dict, kitchen_id: str) -> tuple[dict, dict]:  # type: ignore[no-untyped-def]
    """The customer app's bag: quote, then POST /orders with the quote's token (no payment call after)."""
    lat, lng = cmd.CENTRES["US"]
    home = {"lat": lat + 0.01, "lng": lng}
    menu = (await client.get(f"/api/v1/restaurants/{kitchen_id}/menu", headers=h)).json()
    item = menu["categories"][0]["items"][0]
    cart = [{"menu_item_id": item["id"], "quantity": 2}]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": kitchen_id, "items": cart,
                                                                     "deliver_to": home, "tip": "2"})
    assert q.status_code == 200, q.text
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": kitchen_id, "items": cart, "payment_method": "card", "quote_token": q.json()["token"],
        "delivery_address": {"street": "1 Review Way", "city": cmd.CITY_NAME, "state": "Idaho", "zip": "00000",
                             "country": "US", **home}})
    assert r.status_code == 201, r.text
    return q.json(), r.json()


async def step(client: AsyncClient, order_id: str, what: str):  # type: ignore[no-untyped-def]
    """What the worker's review simulator sends: a signed internal call."""
    from shared import internal_auth

    path = f"/api/v1/internal/review/orders/{order_id}/step"
    body = json.dumps({"step": what}).encode()
    return await client.post(path, content=body, headers={"content-type": "application/json",
                                                           **internal_auth.sign("POST", path, body)})


async def test_a_review_order_costs_nothing_and_is_placed_without_a_payment_provider(client: AsyncClient, monkeypatch) -> None:
    from core_api.modules.pricing.service.engine import REVIEW_LABEL

    cmd, logins, emails = await make_review_city()
    try:
        calls = no_providers(monkeypatch)
        h = await bearer(client, logins["BhojanGo"].email, logins["BhojanGo"].password)
        kitchen = await review_kitchen(client, cmd, h)
        quote, order = await quote_and_order(client, cmd, h, kitchen["id"])

        # The bill: every usual line (food, delivery, the tip...), then the review line; total 0.00.
        codes = [ln["code"] for ln in quote["lines"]]
        assert codes[0] == "food" and "tip" in codes and "delivery_fee" in codes, codes
        last = quote["lines"][-1]
        assert (last["code"], last["label"], last["funded_by"]) == ("promotion", REVIEW_LABEL, "platform")
        assert Decimal(quote["total"]) == 0 and Decimal(last["amount"]) == -sum(Decimal(ln["amount"]) for ln in quote["lines"][:-1])
        assert Decimal(quote["lines"][0]["amount"]) > 0

        # Placed at once: no PaymentIntent at a provider, nothing charged, no provider called.
        assert order["status"] == "placed", order
        assert Decimal(str(order["total"])) == 0
        assert calls == []
        st = (await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=h)).json()
        assert (st["payment_status"], st["amount"], st["order_status"]) == ("succeeded", 0, "placed"), st
        pay = (await client.get(f"/api/v1/payments/{order['id']}", headers=h)).json()
        assert pay["provider"] == "review" and pay["amount"] == 0, pay
        # Nothing left to pay: the app's checkout can't open a provider for it.
        again = await client.post("/api/v1/payments/initiate", headers=h, json={"order_id": order["id"], "payment_method_type": "card"})
        assert again.status_code == 409 and calls == []
        bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=h)).json()
        assert Decimal(bill["total"]) == 0 and bill["lines"][-1]["label"] == REVIEW_LABEL

        # The review simulator's steps move it, as the kitchen and the review delivery partner.
        for what, status in (("accept", "accepted"), ("prepare", "preparing"), ("assign", "preparing"), ("ready", "ready"),
                             ("pick_up", "picked_up"), ("deliver", "delivered")):
            r = await step(client, order["id"], what)
            assert r.status_code == 200 and r.json()["status"] == status, (what, r.text)
        mine = (await client.get(f"/api/v1/orders/{order['id']}", headers=h)).json()
        assert mine["status"] == "delivered"
        rider = await bearer(client, logins["BhojanGo Delivery"].email, logins["BhojanGo Delivery"].password)
        me = (await client.get("/api/v1/users/me", headers=rider)).json()
        assert str(mine["driver_id"]) == str(me["id"])
        # A step out of order is refused; it never skips.
        assert (await step(client, order["id"], "accept")).status_code == 409
        # Cancelling a review order refunds nothing at any provider (there was nothing to charge).
        _, second = await quote_and_order(client, cmd, h, kitchen["id"])
        r = await client.post(f"/api/v1/orders/{second['id']}/cancel", headers=h, json={"reason": "other"})
        assert r.status_code == 200 and r.json()["status"] == "cancelled" and calls == [], r.text
    finally:
        await remove(CODE, emails)


async def test_everyone_else_pays_and_the_review_steps_refuse_their_orders(client: AsyncClient) -> None:
    from core_api.integration.test_orders_flow import login, new_order, pay
    from core_api.modules.pricing.service.engine import REVIEW_LABEL

    cmd, logins, emails = await make_review_city()
    try:
        review_h = await bearer(client, logins["BhojanGo"].email, logins["BhojanGo"].password)
        kitchen = await review_kitchen(client, cmd, review_h)
        other = await login(client, "customer1.boi@example.com")

        # A normal customer can't price (so can't order) in the review city, even with the kitchen's id.
        lat, lng = cmd.CENTRES["US"]
        menu = (await client.get(f"/api/v1/restaurants/{kitchen['id']}/menu", headers=review_h)).json()
        item = menu["categories"][0]["items"][0]
        q = await client.post("/api/v1/pricing/quote", headers=other, json={
            "restaurant_id": kitchen["id"], "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "deliver_to": {"lat": lat + 0.01, "lng": lng}})
        assert q.status_code == 422, q.text

        # A normal customer in a normal city pays: a total above zero, waiting for payment, then paid.
        h = await login(client, "customer1.hyd@example.com")
        order = await new_order(client, h)
        assert order["status"] == "pending_payment" and Decimal(str(order["total"])) > 0
        bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=h)).json()
        assert REVIEW_LABEL not in [ln["label"] for ln in bill["lines"]]
        await pay(client, h, order)
        assert (await client.get(f"/api/v1/orders/{order['id']}", headers=h)).json()["status"] == "placed"

        # The review customer pays too, outside the review city.
        theirs = await new_order(client, review_h)
        assert theirs["status"] == "pending_payment" and Decimal(str(theirs["total"])) > 0

        # The review steps refuse every order that isn't a review order: a normal customer's, and
        # the review customer's own in a normal city. Nothing about them changes.
        for o, who in ((order, h), (theirs, review_h)):
            for what in ("accept", "prepare", "assign", "ready", "pick_up", "deliver"):
                r = await step(client, o["id"], what)
                assert r.status_code == 404, (what, r.text)
        assert (await client.get(f"/api/v1/orders/{order['id']}", headers=h)).json()["status"] == "placed"
        assert (await client.get(f"/api/v1/orders/{theirs['id']}", headers=review_h)).json()["status"] == "pending_payment"
        # And unsigned, nobody may call it.
        r = await client.post(f"/api/v1/internal/review/orders/{order['id']}/step", json={"step": "accept"}, headers=h)
        assert r.status_code == 401
    finally:
        await remove(CODE, emails)
