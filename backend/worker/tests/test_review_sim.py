"""R20: the review simulator (app/demo_sim/review.py), the parts without a database:
when it runs, what it does next to a review order, and that it reads review orders only.
On Postgres with core_api in-process: tests/integration/test_review_sim_db.py."""
from datetime import UTC, datetime, timedelta

import pytest

from app.demo_sim import review as R

T0 = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)


def order(status: str, **kw) -> R.ReviewOrder:  # type: ignore[no-untyped-def]
    return R.ReviewOrder(id="o1", status=status, driver_id=kw.pop("driver_id", None), created_at=T0, **kw)


@pytest.mark.parametrize(("flag", "on"), [("1", True), ("true", True), (True, True), ("0", False), ("", False),
                                          (None, False), (False, False)])
def test_on_only_when_review_sim_says_so(flag, on) -> None:  # type: ignore[no-untyped-def]
    assert R.enabled(flag)[0] is on


def test_production_starts_with_review_sim_but_not_with_the_demo_rider(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The one simulator production allows; DEMO_RIDER_SIM is still refused there."""
    from app.demo_sim import rules
    from shared.config import ProductionConfigError, Settings

    live = {"APP_ENV": "production", "PAYMENT_PROVIDER": "live", "PAYOUT_PROVIDER": "live", "OTP_FIXED_CODE": "",
            "DELIVERY_PIN_FIXED": "", "REVIEW_SIM": "1"}
    for k, v in live.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("DEMO_RIDER_SIM", raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert R.enabled(s.worker.REVIEW_SIM) == (True, "on")
    assert rules.enabled(True, "production", {})[0] is False  # the demo rider's own guard
    monkeypatch.setenv("DEMO_RIDER_SIM", "1")
    with pytest.raises(ProductionConfigError, match="DEMO_RIDER_SIM"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_the_whole_order_at_a_believable_pace() -> None:
    placed = order("placed", placed_at=T0)
    assert R.next_step(placed, T0 + timedelta(seconds=5)) == "wait"
    assert R.next_step(placed, T0 + R.ACCEPT_AFTER) == "accept"
    assert R.next_step(order("accepted", accepted_at=T0), T0) == "prepare"
    # The review delivery partner is assigned while the food cooks (so dispatch never offers it to anyone).
    assert R.next_step(order("preparing", accepted_at=T0), T0) == "assign"
    cooking = order("preparing", accepted_at=T0, driver_id="r1")
    assert R.next_step(cooking, T0 + timedelta(minutes=1)) == "wait"
    assert R.next_step(cooking, T0 + R.READY_AFTER) == "ready"
    assert R.next_step(order("almost_ready", accepted_at=T0, driver_id="r1"), T0 + R.READY_AFTER) == "ready"
    ready = order("ready", ready_at=T0, driver_id="r1")
    assert R.next_step(ready, T0 + timedelta(seconds=10)) == "wait"
    assert R.next_step(ready, T0 + R.PICK_UP_AFTER) == "pick_up"
    assert R.next_step(order("ready", ready_at=T0), T0 + R.PICK_UP_AFTER) == "assign"  # never picked up riderless
    riding = order("picked_up", picked_up_at=T0, driver_id="r1")
    assert R.next_step(riding, T0 + timedelta(minutes=1)) == "wait"
    assert R.next_step(riding, T0 + R.DELIVER_AFTER) == "deliver"
    for done in ("delivered", "cancelled", "pending_payment"):
        assert R.next_step(order(done), T0 + timedelta(hours=1)) == "wait"
    total = R.ACCEPT_AFTER + R.READY_AFTER + R.PICK_UP_AFTER + R.DELIVER_AFTER
    assert total <= timedelta(minutes=8)  # a reviewer sees it all in a few minutes


def test_it_reads_review_orders_only() -> None:
    """A review-only city, and both the customer and the kitchen's owner are its review accounts."""
    sql = str(R.ORDERS_SQL)
    assert "settings->>'review_only' = 'true'" in sql
    assert "review_accounts' @> jsonb_build_array(o.customer_id::text)" in sql
    assert "review_accounts' @> jsonb_build_array(r.owner_id::text)" in sql
    assert R.STEP_PATH == "/api/v1/internal/review/orders/{order_id}/step"


async def test_one_failing_order_never_stops_the_others(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    orders = [order("placed", placed_at=T0), R.ReviewOrder(id="o2", status="accepted", driver_id=None, created_at=T0)]

    async def review_orders():  # type: ignore[no-untyped-def]
        return orders

    sent = []

    async def send(core, order_id, step):  # type: ignore[no-untyped-def]
        sent.append((order_id, step))
        if order_id == "o1":
            raise RuntimeError("boom")
        return {"status": "preparing"}

    monkeypatch.setattr(R, "review_orders", review_orders)
    monkeypatch.setattr(R, "send", send)
    assert await R.tick(None, T0 + timedelta(minutes=1)) == [("o2", "prepare")]
    assert sent == [("o1", "accept"), ("o2", "prepare")]
