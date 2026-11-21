"""R27: a kitchen's tablet heartbeat (shared/kitchen_live.py): live for 60 s after a beat, the
gap recorded when it comes back, the demo simulator's beat only for kitchens no tablet runs,
and where a tablet is required at all."""
import time

import fakeredis
import pytest

from shared import kitchen_live as K
from shared.config import get_settings

RID = "6b7f3c1e-0000-4000-8000-000000000001"


@pytest.fixture
def r():  # type: ignore[no-untyped-def]
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_live_for_60_seconds_after_a_heartbeat(r) -> None:  # type: ignore[no-untyped-def]
    now = time.time()
    assert (await K.status(RID, r, now)).live is False, "never heard from: not live"
    await K.beat(RID, "poll", r, now)
    s = await K.status(RID, r, now + 59)
    assert s.live and s.via == "poll" and not s.by_simulator
    assert (await K.status(RID, r, now + 61)).live is False, "silent for over 60 s: paused"


async def test_coming_back_records_the_gap(r) -> None:  # type: ignore[no-untyped-def]
    now = time.time()
    await K.beat(RID, "socket", r, now)
    await K.beat(RID, "socket", r, now + 10)
    assert (await K.status(RID, r, now + 10)).gap_from is None, "a beat 10 s later is no gap"
    await K.beat(RID, "poll", r, now + 310)
    s = await K.status(RID, r, now + 310)
    assert s.live
    assert s.gap_from is not None and s.gap_to is not None
    assert abs(s.gap_from.timestamp() - (now + 10 + K.LIVE_SECONDS)) < 1, "paused from 60 s after the last beat"
    assert abs(s.gap_to.timestamp() - (now + 310)) < 1, "to the beat that brought it back"


async def test_the_demo_simulator_keeps_only_kitchens_no_tablet_runs_live(r) -> None:  # type: ignore[no-untyped-def]
    now = time.time()
    await K.sim_beat([RID], r)
    s = await K.status(RID, r, now)
    assert s.live and s.by_simulator, "a demo kitchen with no tablet: the simulator keeps it open"
    # A real tablet runs it (R26: Morning Ridge Bakery on the lead's tablet), then goes quiet:
    await K.beat(RID, "socket", r, now - 120)
    await K.sim_beat([RID], r)
    s = await K.status(RID, r, now)
    assert s.live is False and not s.by_simulator, "the simulator never keeps a tablet's kitchen open"


def test_required_by_environment(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = get_settings()
    for env, flag, want in (("qa", "auto", True), ("production", "auto", True), ("staging", "auto", True),
                            ("development", "auto", False), ("test", "auto", False), ("local", "auto", False),
                            ("development", "1", True), ("production", "0", False)):
        monkeypatch.setattr(s, "APP_ENV", env)
        monkeypatch.setattr(s.catalog, "KITCHEN_TABLET_REQUIRED", flag)
        assert K.required() is want, (env, flag)
