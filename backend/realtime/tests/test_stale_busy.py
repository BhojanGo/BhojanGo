"""A rider left busy with an order that is over or gone is freed when they go online
or offline (QA, 2026-11-15: a reset rebuilt the database but not realtime's Redis,
the demo rider stayed busy with an order that no longer existed, and dispatch never
offered it anything again: "no_rider_available" every 15 s for hours)."""
import pytest

from app.services import dispatch
from app.services.core_api import CoreApiError
from tests.test_dispatch import ORDER, RIDER_NEAR, SPICE_ROUTE, core, info, r  # noqa: F401

GHOST = "00000000-0000-0000-0000-00000000beef"  # not in core_api any more


async def busy_with(r, order: str) -> None:  # type: ignore[no-untyped-def]
    await r.hset(dispatch.state_key(RIDER_NEAR), mapping={"status": "busy", "order_id": order})


async def test_busy_with_an_order_that_is_gone(r, core) -> None:  # type: ignore[no-untyped-def]
    await busy_with(r, GHOST)
    state = await dispatch.go_online(RIDER_NEAR, SPICE_ROUTE[0] + 0.004, SPICE_ROUTE[1])
    assert state["status"] == "available"
    await dispatch.start_dispatch(ORDER)  # and it gets offers again
    assert (await dispatch.rider_state(RIDER_NEAR))["status"] == "offered"


@pytest.mark.parametrize("change", [{"status": "delivered"}, {"status": "cancelled"},
                                    {"status": "picked_up", "driver_id": "someone-else"}])
async def test_busy_with_an_order_that_is_over_or_not_theirs(r, core, monkeypatch, change) -> None:  # type: ignore[no-untyped-def]
    async def dispatch_info(order: str) -> dict:
        return info(**{"order_id": order, "driver_id": RIDER_NEAR, **change})

    monkeypatch.setattr(core, "dispatch_info", dispatch_info)
    await busy_with(r, ORDER)
    assert (await dispatch.go_offline(RIDER_NEAR))["status"] == "offline", "free to go offline"


async def test_a_real_delivery_keeps_the_rider_busy(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def dispatch_info(order: str) -> dict:
        return info(order_id=order, driver_id=RIDER_NEAR, status="picked_up")

    monkeypatch.setattr(core, "dispatch_info", dispatch_info)
    await busy_with(r, ORDER)
    assert (await dispatch.go_online(RIDER_NEAR, *SPICE_ROUTE))["status"] == "busy"
    with pytest.raises(ValueError):
        await dispatch.go_offline(RIDER_NEAR)


async def test_when_core_api_cannot_answer_nothing_changes(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def dispatch_info(order: str) -> dict:
        raise CoreApiError(503, "down")

    monkeypatch.setattr(core, "dispatch_info", dispatch_info)
    await busy_with(r, GHOST)
    assert not await dispatch.free_if_stale(RIDER_NEAR)
    assert (await dispatch.rider_state(RIDER_NEAR))["status"] == "busy"


async def test_a_batch_is_left_alone(r, core) -> None:  # type: ignore[no-untyped-def]
    await r.hset(dispatch.state_key(RIDER_NEAR), mapping={"status": "busy", "order_id": GHOST, "batch": f"{GHOST},{ORDER}"})
    assert not await dispatch.free_if_stale(RIDER_NEAR)
