"""Driver shift / availability time tracking, backed by Redis.

delivery-svc is intentionally stateless (Redis + DynamoDB), so shift accounting
lives in Redis rather than a relational table. We track:
  - available_minutes: total time logged in & online
  - active_minutes:    time in the "active" state (on a delivery)
  - waiting_minutes:   time in the "waiting"/idle state

Elapsed time is accumulated into the *previous* state whenever the state changes
or the shift ends.
"""
from __future__ import annotations

from app.core.redis import get_redis

ACTIVE = "active"
WAITING = "waiting"
AVAILABLE = "available"
_STATES = {ACTIVE, WAITING, AVAILABLE, "idle"}


def _shift_key(driver_id: str) -> str:
    return f"driver:{driver_id}:shift"


def _accumulate(shift: dict, now: float) -> dict:
    """Fold the time since last_event into the bucket for the current state."""
    last = float(shift.get("last_event_at", now))
    elapsed = max(0.0, now - last)
    state = shift.get("status", AVAILABLE)
    if state == ACTIVE:
        shift["active_seconds"] = float(shift.get("active_seconds", 0)) + elapsed
    elif state in (WAITING, "idle"):
        shift["waiting_seconds"] = float(shift.get("waiting_seconds", 0)) + elapsed
    shift["last_event_at"] = now
    return shift


async def start_shift(driver_id: str, now: float) -> dict:
    redis = await get_redis()
    mapping = {
        "online_at": now,
        "status": AVAILABLE,
        "active_seconds": 0.0,
        "waiting_seconds": 0.0,
        "last_event_at": now,
    }
    await redis.hset(_shift_key(driver_id), mapping={k: str(v) for k, v in mapping.items()})
    return await get_shift(driver_id, now)


async def set_activity(driver_id: str, status: str, now: float) -> dict:
    if status not in _STATES:
        raise ValueError(f"invalid status: {status}")
    redis = await get_redis()
    raw = await redis.hgetall(_shift_key(driver_id))
    if not raw:
        raise LookupError("no active shift")
    shift = _accumulate(dict(raw), now)
    shift["status"] = status
    await redis.hset(_shift_key(driver_id), mapping={k: str(v) for k, v in shift.items()})
    return await get_shift(driver_id, now)


async def get_shift(driver_id: str, now: float) -> dict:
    redis = await get_redis()
    raw = await redis.hgetall(_shift_key(driver_id))
    if not raw:
        return {"driver_id": driver_id, "online": False}
    snapshot = _accumulate(dict(raw), now)  # do not persist; just for the read
    online_at = float(snapshot["online_at"])
    available_minutes = int((now - online_at) // 60)
    return {
        "driver_id": driver_id,
        "online": True,
        "status": snapshot.get("status", AVAILABLE),
        "available_minutes": available_minutes,
        "active_minutes": int(float(snapshot.get("active_seconds", 0)) // 60),
        "waiting_minutes": int(float(snapshot.get("waiting_seconds", 0)) // 60),
    }


async def end_shift(driver_id: str, now: float) -> dict:
    summary = await get_shift(driver_id, now)
    redis = await get_redis()
    await redis.delete(_shift_key(driver_id))
    summary["online"] = False
    return summary
