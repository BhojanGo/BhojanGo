"""P15: which events message whom."""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.services.directory import Person
from app.services.dispatcher import POLICY, plan

ORDER = uuid.UUID("ab12cd34-0000-4000-8000-000000000001")
CUSTOMER, OWNER, RIDER, REST = (str(uuid.uuid4()) for _ in range(4))


class FakeDirectory:
    def __init__(self) -> None:
        self.row = {"id": ORDER, "customer_id": CUSTOMER, "restaurant_id": REST, "restaurant_name": "Spice Route Kitchen",
                    "total": Decimal("638.22"), "currency": "INR", "market_city": "IN-TG-HYD",
                    "estimated_delivery_time": datetime(2026, 11, 14, 14, 54, tzinfo=UTC),
                    "accept_due_at": datetime(2026, 11, 14, 14, 33, tzinfo=UTC), "driver_id": RIDER,
                    "items": [{"quantity": 2}, {"quantity": 1}]}

    async def order(self, order_id):  # type: ignore[no-untyped-def]
        return self.row if order_id == str(ORDER) else None

    async def restaurant_owner(self, rid):  # type: ignore[no-untyped-def]
        return OWNER if rid == REST else None

    async def timezone(self, city, country=None):  # type: ignore[no-untyped-def]
        return "Asia/Kolkata"

    async def person(self, uid):  # type: ignore[no-untyped-def]
        return Person(uuid.UUID(uid), "Imran Shaikh", None, "+9190000201", "en-IN", "IN") if uid == RIDER else None

    async def payout_period(self, run_id):  # type: ignore[no-untyped-def]
        return (date(2026, 11, 3), date(2026, 11, 10))


def ev(kind: str, **payload) -> dict:  # type: ignore[no-untyped-def]
    return {"event_type": kind, "event_id": str(uuid.uuid4()), "payload": {"order_id": str(ORDER), **payload}}


async def test_placed_tells_customer_and_restaurant() -> None:
    out = await plan(ev("order.placed"), FakeDirectory())  # type: ignore[arg-type]
    assert [(o.user_id, o.key) for o in out] == [(CUSTOMER, "order_placed"), (OWNER, "partner_new_order")]
    assert out[0].total == "₹638.22" and out[0].params["code"] == "#AB12CD"
    assert out[1].params == {"code": "#AB12CD", "items": 3, "total": "₹638.22", "accept_by": "8:03 PM"}


async def test_status_changes() -> None:
    d = FakeDirectory()
    assert (await plan(ev("order.status_changed", new_status="preparing"), d))[0].params["eta"] == "8:24 PM"  # type: ignore[arg-type]
    picked = (await plan(ev("order.status_changed", new_status="picked_up"), d))[0]  # type: ignore[arg-type]
    assert picked.key == "order_picked_up" and picked.params["rider"] == "Imran"
    for quiet in ("almost_ready", "ready", "placed"):
        assert await plan(ev("order.status_changed", new_status=quiet), d) == []  # type: ignore[arg-type]
    newer = (await plan(ev("order.status_changed", new_status="accepted",  # type: ignore[arg-type]
                           estimated_delivery_time="2026-11-14T15:10:00+00:00"), d))[0]
    assert newer.params["eta"] == "8:40 PM"  # the event's estimate wins


async def test_cancellations_say_whether_money_moved() -> None:
    d = FakeDirectory()
    refunded = (await plan(ev("order.cancelled", refund_amount=63822), d))[0]  # type: ignore[arg-type]
    assert refunded.key == "order_cancelled_refunded" and refunded.params["refund"] == "₹638.22"
    assert (await plan(ev("order.cancelled", refund_amount=0), d))[0].key == "order_cancelled_unpaid"  # type: ignore[arg-type]


async def test_refunds_only_by_item_get_their_own_message() -> None:
    d = FakeDirectory()
    assert await plan(ev("payment.refunded", amount=63822, currency="INR", reason="restaurant_timeout"), d) == []  # type: ignore[arg-type]
    item = (await plan(ev("payment.refunded", amount=18700, currency="INR", items=[{"id": "x"}]), d))[0]  # type: ignore[arg-type]
    assert item.key == "refund_items" and item.params["amount"] == "₹187.00"


async def test_rider_assigned_and_payment_failed() -> None:
    d = FakeDirectory()
    a = (await plan(ev("driver.assigned", driver_name="Ravi Kumar"), d))[0]  # type: ignore[arg-type]
    assert a.key == "driver_assigned" and a.params["rider"] == "Ravi"
    assert (await plan(ev("payment.failed"), d))[0].key == "payment_failed"  # type: ignore[arg-type]


async def test_payout_goes_to_the_restaurant_owner_or_rider() -> None:
    d = FakeDirectory()
    base = {"event_type": "payout.paid", "payload": {"run_id": "r", "statement_id": "s", "amount": "1240.50",
                                                      "currency": "INR", "user_id": None}}
    rest = await plan({**base, "payload": {**base["payload"], "payee_type": "restaurant", "payee_id": REST}}, d)  # type: ignore[arg-type]
    rider = await plan({**base, "payload": {**base["payload"], "payee_type": "rider", "payee_id": RIDER}}, d)  # type: ignore[arg-type]
    assert rest[0].user_id == OWNER and rider[0].user_id == RIDER
    assert rest[0].params == {"amount": "₹1,240.50", "period": "3–9 Nov"}


async def test_payout_setup_link_goes_to_the_owner_or_delivery_partner() -> None:
    d = FakeDirectory()
    link = "https://api.example/api/v1/finance/payout-onboarding?t=abc"
    base = {"event_type": "payout.setup_link", "payload": {"link": link, "provider": "stripe_connect", "user_id": None}}
    rest = await plan({**base, "payload": {**base["payload"], "payee_type": "restaurant", "payee_id": REST}}, d)  # type: ignore[arg-type]
    rider = await plan({**base, "payload": {**base["payload"], "payee_type": "rider", "payee_id": RIDER}}, d)  # type: ignore[arg-type]
    assert rest[0].user_id == OWNER and rider[0].user_id == RIDER
    assert rest[0].key == "payout_setup" and rest[0].params == {"link": link} and rest[0].data["screen"] == "payouts"


async def test_unknown_orders_and_events_are_ignored() -> None:
    d = FakeDirectory()
    assert await plan({"event_type": "order.placed", "payload": {"order_id": str(uuid.uuid4())}}, d) == []  # type: ignore[arg-type]
    assert await plan(ev("order.created"), d) == []  # type: ignore[arg-type]


def test_sms_only_where_it_matters() -> None:
    always_sms = [k for k, c in POLICY.items() if "sms" in c]
    assert always_sms == []  # SMS costs money: only as a fallback
    assert {k for k, c in POLICY.items() if "sms_fallback" in c} == {
        "order_picked_up", "order_cancelled_refunded", "order_cancelled_unpaid", "payment_failed", "partner_new_order",
        "order_ready_for_pickup"}  # R32: the customer needs the pickup code


async def test_quick_message_goes_to_the_other_person_by_push_only() -> None:
    from app.services import messages as m
    from app.services.dispatcher import NO_INBOX

    out = await plan(ev("order.message", to_user_id=CUSTOMER, from_name="Imran", text="I'm outside.",  # type: ignore[arg-type]
                        message_id="m1"), FakeDirectory())
    assert [(o.user_id, o.key) for o in out] == [(CUSTOMER, "order_message")]
    assert out[0].params == {"name": "Imran", "text": "I'm outside."} and out[0].data == {"message_id": "m1"}
    r = m.render("order_message", "te", **out[0].params)
    assert r.title == "Imran నుండి సందేశం" and r.body == "I'm outside."
    # Pushed, never kept in the inbox: the conversation is gone once the order is delivered.
    assert POLICY["order_message"] == ("push",) and "order_message" in NO_INBOX


async def test_almost_there_tells_the_customer() -> None:
    """realtime's driver.almost_there (the rider is ~400 m from the door): in-app and push. No SMS
    (it costs money; "on the way" already went by SMS to anyone without the app), no email."""
    from app.services import messages as m

    d = FakeDirectory()
    [out] = await plan(ev("driver.almost_there", driver_id=RIDER, distance_m=320, eta_minutes=2), d)  # type: ignore[arg-type]
    assert (out.user_id, out.key, out.params["rider"]) == (CUSTOMER, "order_almost_there", "Imran")
    assert POLICY["order_almost_there"] == ("push",)
    assert out.total is None, "not a receipt: no email"
    en = m.render(out.key, "en", **out.params)
    assert (en.title, en.body) == ("Almost there", "Imran is a couple of minutes away with your order from Spice Route Kitchen.")
    assert "Imran" in m.render(out.key, "te", **out.params).body and "Spice Route Kitchen" in m.render(out.key, "hi", **out.params).body
    d.row = {**d.row, "driver_id": None}
    out = await plan(ev("driver.almost_there"), d)  # type: ignore[arg-type]
    assert out[0].params["rider"] is None  # the message says "Your delivery partner" in the customer's language
    assert m.render(out[0].key, "en", **out[0].params).body.startswith("Your delivery partner is a couple of minutes away")
    assert await plan({"event_type": "driver.almost_there", "payload": {"order_id": str(uuid.uuid4())}}, d) == []  # type: ignore[arg-type]


async def test_a_preset_quick_message_reaches_the_other_person_in_their_language() -> None:
    """Round 5: the rider taps "I'm outside." in Hindi; a Telugu customer reads it in Telugu."""
    from app.services import messages as m

    out = await plan(ev("order.message", to_user_id=CUSTOMER, from_name="", from_role="rider", preset="outside",  # type: ignore[arg-type]
                        text="I'm outside.", message_id="m2"), FakeDirectory())
    assert out[0].params == {"name": "", "text": "I'm outside.", "preset": "outside", "from_role": "rider"}
    r = m.render("order_message", "te", **out[0].params)
    assert (r.title, r.body) == ("మీ డెలివరీ పార్ట్‌నర్ నుండి సందేశం", "నేను బయట ఉన్నాను.")


async def test_incident_messages_go_to_each_customer_in_their_language() -> None:  # R17
    from app.services import messages as m

    d = FakeDirectory()
    out = (await plan(ev("incident.message", user_id=CUSTOMER, template="refund_sent",  # type: ignore[arg-type]
                         params={"amount": "₹319.11"}, bulk_message_id="b1"), d))[0]
    assert (out.user_id, out.key, out.order_id) == (CUSTOMER, "incident_refund_sent", str(ORDER))
    assert out.params == {"amount": "₹319.11", "code": "#AB12CD", "restaurant": "Spice Route Kitchen"}
    assert POLICY["incident_refund_sent"] == ("push", "email") and out.data == {"bulk_message_id": "b1"}
    en, hi = m.render(out.key, "en", **out.params), m.render(out.key, "hi", **out.params)
    assert "#AB12CD" in en.body and "₹319.11" in en.body and "Spice Route Kitchen" in en.body
    assert "₹319.11" in hi.body and hi.title == "रिफंड भेजा गया"
    # a city's customers: no order, the admin's words only
    city = (await plan({"event_type": "incident.message", "event_id": "e2", "payload": {  # type: ignore[arg-type]
        "user_id": CUSTOMER, "order_id": None, "template": "area_paused", "params": {"area": "Hyderabad"}}}, d))[0]
    assert city.order_id is None and m.render(city.key, "te", **city.params).body.startswith("ఒక సమస్యను")
    assert {f"incident_{k}" for k in m.INCIDENT_MESSAGES} <= set(POLICY)


async def test_pickup_ready_sends_the_code_and_collected_is_the_receipt() -> None:
    """R32: a pickup order's customer is told it's ready with the pickup code (push, SMS if no app); when the
    restaurant enters the code, the receipt says it was collected. A delivery order's "ready" stays silent."""
    from app.services import messages as m

    d = FakeDirectory()
    d.row = {**d.row, "fulfillment": "pickup", "delivery_pin": "4821", "driver_id": None}
    ready = await plan(ev("order.status_changed", new_status="ready"), d)  # type: ignore[arg-type]
    assert [(o.user_id, o.key, o.params["pin"]) for o in ready] == [(CUSTOMER, "order_ready_for_pickup", "4821")]
    assert POLICY["order_ready_for_pickup"] == ("push", "sms_fallback")
    assert "4821" in m.render("order_ready_for_pickup", "te", **ready[0].params).body
    done = await plan(ev("order.status_changed", new_status="delivered"), d)  # type: ignore[arg-type]
    assert [o.key for o in done] == ["order_collected"] and done[0].total == "₹638.22"
    assert await plan(ev("order.status_changed", new_status="ready"), FakeDirectory()) == []  # type: ignore[arg-type]


async def test_food_permit_reminder_goes_to_the_owner_in_their_language() -> None:  # R39
    from app.services import messages as m

    out = await plan({"event_type": "restaurant.permit_expiring", "payload": {  # type: ignore[arg-type]
        "restaurant_id": REST, "owner_id": OWNER, "restaurant": "Boise Bowl Co.", "expires_on": "2026-12-24", "days_left": 30}},
        FakeDirectory())
    assert [(o.user_id, o.key, o.params) for o in out] == [(OWNER, "permit_expiring", {"restaurant": "Boise Bowl Co.", "date": "24 Dec 2026"})]
    assert POLICY["permit_expiring"] == ("push", "email")
    en = m.render("permit_expiring", "en", restaurant="Boise Bowl Co.", date="24 Dec 2026")
    assert en.title == "Renew your food permit" and "expires on 24 Dec 2026" in en.body and "BhojanGo Restaurant app" in en.body
    assert "24 Dec 2026" in m.render("permit_expiring", "es", restaurant="X", date="24 Dec 2026").body
    assert await plan({"event_type": "restaurant.permit_expiring", "payload": {"restaurant_id": REST}}, FakeDirectory()) == []  # type: ignore[arg-type]
