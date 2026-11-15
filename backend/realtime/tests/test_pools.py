"""Dispatch pools (Round 5, item 3): the demo rider simulator has riders of its own.
Its orders go only to its riders; its riders never get anyone else's order; the demo
riders people test with by hand (and Maestro), and every real rider, never get a
simulator order. Real riders and orders have no pool, so nothing changes for them."""
import json

import pytest

from app.services import dispatch
from tests.test_dispatch import (  # noqa: F401  (fixtures)
    ORDER,
    RIDER_FAR,
    RIDER_MID,
    RIDER_NEAR,
    _pair,
    core,
    r,
)

SIM = "demo_sim"


@pytest.mark.parametrize(("rider", "order", "ok"), [
    (None, None, True),     # a real rider, a real order: as ever
    (SIM, SIM, True),       # the simulator's rider, the simulator's order
    (SIM, None, False),     # the simulator's rider never gets anyone else's order
    (None, SIM, False),     # a demo rider tested by hand (or a real one) never gets the simulator's
    ("", None, True),       # an empty value is no pool
])
def test_same_pool(rider, order, ok) -> None:  # type: ignore[no-untyped-def]
    assert dispatch.same_pool(rider, order) is ok


async def test_a_simulator_order_goes_only_to_a_simulator_rider(r, core) -> None:  # type: ignore[no-untyped-def]
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)              # the demo rider someone is testing with
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960, pool=SIM)     # further away, but the simulator's
    await dispatch.mark_order_pool(ORDER, SIM)
    assert await dispatch.start_dispatch(ORDER) == RIDER_MID
    assert await dispatch.current_offer(RIDER_NEAR) is None
    assert (await dispatch.rider_state(RIDER_NEAR))["status"] == "available"


async def test_a_simulator_order_waits_when_no_simulator_rider_is_free(r, core) -> None:  # type: ignore[no-untyped-def]
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    await dispatch.mark_order_pool(ORDER, SIM)
    assert await dispatch.start_dispatch(ORDER) is None
    assert await r.zscore(dispatch.RETRY, ORDER) is not None, "retried later, never given to a person"
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960, pool=SIM)  # a simulator rider comes online
    assert (await dispatch.current_offer(RIDER_MID))["order_id"] == ORDER


async def test_an_ordinary_order_never_goes_to_a_simulator_rider(r, core) -> None:  # type: ignore[no-untyped-def]
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940, pool=SIM)  # nearest, but the simulator's
    assert await dispatch.start_dispatch(ORDER) is None
    assert await dispatch.current_offer(RIDER_NEAR) is None
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960)
    assert (await dispatch.current_offer(RIDER_MID))["order_id"] == ORDER, "the first real rider free gets it"
    assert await dispatch.current_offer(RIDER_NEAR) is None


async def test_the_pool_comes_from_each_go_online(r, core) -> None:  # type: ignore[no-untyped-def]
    await dispatch.go_online(RIDER_FAR, 17.4520, 78.3940, pool=SIM)
    assert await dispatch.rider_pool(RIDER_FAR) == SIM
    await dispatch.go_online(RIDER_FAR, 17.4520, 78.3940)  # core_api no longer says so
    assert await dispatch.rider_pool(RIDER_FAR) is None
    with pytest.raises(ValueError):
        await dispatch.mark_order_pool(ORDER, "someone")


async def test_a_batch_never_mixes_pools(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = await _pair(core)
    await dispatch.mark_order_pool(orders[1], SIM)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    assert await dispatch.offer_batch(orders) is None


async def test_online_takes_the_pool_core_api_gives(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from shared.auth import CurrentUser

    async def ready(rider: str) -> dict:
        return {"rider_id": rider, "ready": True, "country": "IN", **({"pool": SIM} if rider == RIDER_MID else {})}

    monkeypatch.setattr(core, "rider_ready", ready)
    from app.core import auth

    for rider in (RIDER_NEAR, RIDER_MID):
        app.dependency_overrides[auth.get_current_user] = lambda rider=rider: CurrentUser(
            user_id=rider, role="driver", country="IN")
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                assert (await c.post("/api/v1/riders/me/online", json={"lat": 17.45, "lng": 78.39})).status_code == 200
        finally:
            app.dependency_overrides.clear()
    assert await dispatch.rider_pool(RIDER_MID) == SIM and await dispatch.rider_pool(RIDER_NEAR) is None


async def test_pool_orders_endpoint_is_signed_and_never_in_production(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    from app.api.v1 import batches
    from app.main import app
    from shared import internal_auth

    path = "/internal/dispatch/pool-orders"
    body = json.dumps({"order_id": ORDER, "pool": SIM}).encode()
    signed = {"content-type": "application/json", **internal_auth.sign("POST", path, body)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post(path, content=body, headers={"content-type": "application/json"})).status_code == 401
        ok = await c.post(path, content=body, headers=signed)
        assert ok.status_code == 200 and await dispatch.order_pool(ORDER) == SIM
        other = json.dumps({"order_id": ORDER, "pool": "vip"}).encode()
        bad = await c.post(path, content=other, headers={"content-type": "application/json",
                                                         **internal_auth.sign("POST", path, other)})
        assert bad.status_code == 422, "only the simulator's pool"

        class Prod:
            production_named = True

        monkeypatch.setattr(batches, "get_settings", lambda: Prod())
        await r.delete(dispatch.order_pool_key(ORDER))
        refused = await c.post(path, content=body, headers={"content-type": "application/json",
                                                             **internal_auth.sign("POST", path, body)})
        assert refused.status_code == 403 and await dispatch.order_pool(ORDER) is None
