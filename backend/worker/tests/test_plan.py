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


async def test_unknown_orders_and_events_are_ignored() -> None:
    d = FakeDirectory()
    assert await plan({"event_type": "order.placed", "payload": {"order_id": str(uuid.uuid4())}}, d) == []  # type: ignore[arg-type]
    assert await plan(ev("order.created"), d) == []  # type: ignore[arg-type]


def test_sms_only_where_it_matters() -> None:
    always_sms = [k for k, c in POLICY.items() if "sms" in c]
    assert always_sms == []  # SMS costs money: only as a fallback
    assert {k for k, c in POLICY.items() if "sms_fallback" in c} == {
        "order_picked_up", "order_cancelled_refunded", "order_cancelled_unpaid", "payment_failed", "partner_new_order"}
