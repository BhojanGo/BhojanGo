"""R27: is a kitchen's tablet live? A kitchen takes orders only while it is.

The kitchen tablet (BhojanGo Kitchen, apps/partner) sends a heartbeat two ways, and either
counts: a ping on its realtime kitchen socket every 10 s (realtime /ws/kitchen/{id}), and every
successful board poll (core_api GET /orders/restaurant/{id} and GET /restaurants/{id}/today by
the kitchen's owner). A kitchen whose tablet has sent nothing for LIVE_SECONDS is paused for
customers ("Not taking orders right now": catalog availability), so nobody can quote, order or
pay for an order nobody will see; it resumes by itself with the next heartbeat.

Stored in Redis, not in a column: a heartbeat every few seconds from every open tablet would be
a row update (and a cache version bump: catalog caches key on restaurant rows) each time, while
Redis keys are cheap, expire by themselves and are already shared by core_api, realtime and the
worker. Losing Redis loses only heartbeats: every kitchen pauses until its tablet's next beat
(seconds later), which fails safe.

Keys:
- ``kitchen:tablet:{id}``: the last tablet heartbeat ({"at": epoch seconds, "via": "socket" | "poll"}),
  kept TABLET_SEEN_SECONDS (12 h). Its presence also says a real tablet runs this kitchen.
- ``kitchen:sim:{id}``: the QA / make dev demo simulator (worker app/demo_sim) says it plays this
  kitchen; expires after LIVE_SECONDS. Counts only for a kitchen no tablet has run in the last
  12 h, so a kitchen opened on a real tablet (R26: Morning Ridge Bakery, Boise) is governed by
  that tablet alone, even though the simulator also plays the demo kitchens.
- ``kitchen:tablet_gap:{id}``: the last time customers couldn't order because the tablet was
  silent ({"from": iso, "to": iso}), for the tablet's own header; kept 12 h.

Kitchens in a review-only city (the app store reviewers', played by the review simulator) are
never paused for this (catalog availability).
"""
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from shared.config import get_settings

LIVE_SECONDS = 60
TABLET_SEEN_SECONDS = 12 * 3600
GAP_SECONDS = 12 * 3600
OFF_ENVS = frozenset({"development", "dev", "local", "test"})


def tablet_key(rid: object) -> str:
    return f"kitchen:tablet:{rid}"


def sim_key(rid: object) -> str:
    return f"kitchen:sim:{rid}"


def gap_key(rid: object) -> str:
    return f"kitchen:tablet_gap:{rid}"


def required() -> bool:
    """Does a kitchen need a live tablet to take orders here (catalog KITCHEN_TABLET_REQUIRED)?"""
    s = get_settings()
    flag = (s.catalog.KITCHEN_TABLET_REQUIRED or "auto").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    return s.APP_ENV.strip().lower() not in OFF_ENVS


_own = None  # a client of its own when KITCHEN_LIVE_REDIS_URL names another Redis database than REDIS_URL


def redis_url() -> str:
    """The Redis URL (and database) of the heartbeats: KITCHEN_LIVE_REDIS_URL, else REDIS_URL. Every
    service must resolve the same one (tests/test_kitchen_live_redis.py checks compose and Railway)."""
    s = get_settings()
    return s.KITCHEN_LIVE_REDIS_URL or s.REDIS_URL


async def redis_client():  # type: ignore[no-untyped-def]
    global _own
    s = get_settings()
    if not s.KITCHEN_LIVE_REDIS_URL or s.KITCHEN_LIVE_REDIS_URL == s.REDIS_URL:
        from shared.redis import get_redis

        return await get_redis()
    if _own is None:
        from redis.asyncio import Redis

        _own = Redis.from_url(s.KITCHEN_LIVE_REDIS_URL, password=s.REDIS_PASSWORD or None, decode_responses=True,
                              max_connections=20)
    return _own


async def _redis(r):  # type: ignore[no-untyped-def]
    return r if r is not None else await redis_client()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


async def beat(rid: object, via: str, r=None, now: float | None = None) -> None:  # type: ignore[no-untyped-def]
    """The kitchen's tablet is here (``via`` "socket" or "poll"). Coming back after more than
    LIVE_SECONDS of silence records the gap (customers couldn't order then)."""
    r = await _redis(r)
    now = time.time() if now is None else now
    raw = await r.get(tablet_key(rid))
    if raw:
        try:
            before = float(json.loads(raw)["at"])
        except (ValueError, KeyError, TypeError):
            before = None
        if before is not None and now - before > LIVE_SECONDS:
            await r.set(gap_key(rid), json.dumps({"from": _iso(before + LIVE_SECONDS), "to": _iso(now)}), ex=GAP_SECONDS)
    await r.set(tablet_key(rid), json.dumps({"at": now, "via": via}), ex=TABLET_SEEN_SECONDS)


async def sim_beat(rids: list, r=None) -> None:  # type: ignore[no-untyped-def,type-arg]
    """The demo simulator plays these kitchens (QA and make dev only: worker app/demo_sim)."""
    if not rids:
        return
    r = await _redis(r)
    pipe = r.pipeline()
    for rid in rids:
        pipe.set(sim_key(rid), str(time.time()), ex=LIVE_SECONDS)
    await pipe.execute()


@dataclass(frozen=True)
class Tablet:
    live: bool
    last_seen: datetime | None  # the last tablet heartbeat (None: no tablet in the last 12 h)
    via: str | None
    by_simulator: bool  # live because the demo simulator plays it (no tablet in the last 12 h)
    gap_from: datetime | None = None  # the last pause for a silent tablet, if any
    gap_to: datetime | None = None


def _read(tablet_raw: str | None, sim_raw: str | None, gap_raw: str | None, now: float) -> Tablet:
    at = via = None
    if tablet_raw:
        try:
            d = json.loads(tablet_raw)
            at, via = float(d["at"]), d.get("via")
        except (ValueError, KeyError, TypeError):
            at = None
    tablet_live = at is not None and now - at <= LIVE_SECONDS
    by_sim = not tablet_raw and bool(sim_raw)
    gap_from = gap_to = None
    if gap_raw:
        try:
            g = json.loads(gap_raw)
            gap_from, gap_to = datetime.fromisoformat(g["from"]), datetime.fromisoformat(g["to"])
        except (ValueError, KeyError, TypeError):
            pass
    return Tablet(live=tablet_live or by_sim, last_seen=datetime.fromtimestamp(at, UTC) if at is not None else None,
                  via=via, by_simulator=by_sim and not tablet_live, gap_from=gap_from, gap_to=gap_to)


async def status(rid: object, r=None, now: float | None = None) -> Tablet:  # type: ignore[no-untyped-def]
    r = await _redis(r)
    tablet_raw, sim_raw, gap_raw = await r.mget(tablet_key(rid), sim_key(rid), gap_key(rid))
    return _read(tablet_raw, sim_raw, gap_raw, time.time() if now is None else now)


async def is_live(rid: object, r=None) -> bool:  # type: ignore[no-untyped-def]
    return (await status(rid, r)).live
