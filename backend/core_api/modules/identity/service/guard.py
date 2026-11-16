"""Rate limits per email / phone / account and the password lockout (Redis).

Per-IP limits are slowapi decorators on the routes (api/v1/*.py). These are the
per-identifier ones, keyed by a hash of the normalised email or phone so the keys
hold no personal data:

  rl:{action}:{hash}   counter for a fixed window
  pw_fail:{hash}       wrong passwords (or two-step codes) in the last LOCKOUT_MINUTES
  pw_lock:{hash}       set while password sign-in is locked (TTL = time left)

The lockout is keyed by the email typed, whether or not an account has it, so a
locked unknown email answers exactly like a locked account.
"""
import hashlib

from shared.config import get_settings
from shared.redis import get_redis


def ident_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:40]


async def hit(action: str, ident: str, *, limit: int, window_seconds: int) -> bool:
    """Count one attempt; False once more than ``limit`` were made in the window."""
    redis = await get_redis()
    key = f"rl:{action}:{ident_hash(ident)}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit


async def locked_for(email: str) -> int:
    """Seconds until password sign-in for ``email`` unlocks; 0 = not locked."""
    redis = await get_redis()
    ttl = await redis.ttl(f"pw_lock:{ident_hash(email)}")
    return max(0, int(ttl or 0))


async def failure(email: str) -> int:
    """Count a wrong password or code. Returns the lock's length in seconds when this
    failure locks the account, else 0."""
    s = get_settings().identity
    window = s.LOCKOUT_MINUTES * 60
    redis = await get_redis()
    h = ident_hash(email)
    count = await redis.incr(f"pw_fail:{h}")
    if count == 1:
        await redis.expire(f"pw_fail:{h}", window)
    if count >= s.LOCKOUT_ATTEMPTS:
        pipe = redis.pipeline()
        pipe.setex(f"pw_lock:{h}", window, "1")
        pipe.delete(f"pw_fail:{h}")
        await pipe.execute()
        return window
    return 0


async def clear(email: str) -> None:
    redis = await get_redis()
    h = ident_hash(email)
    await redis.delete(f"pw_fail:{h}", f"pw_lock:{h}")


# ── sending codes (SMS and email) ────────────────────────────────────────────
# Limited per phone number or email address, not per IP: in India many people share one
# IP behind carrier-grade NAT, so a tight per-IP limit would lock real customers out. The
# per-IP limits on the routes are only a high ceiling against abuse (30/minute, 300/hour).
CODE_SEND_WINDOWS: tuple[tuple[int, int], ...] = ((30, 1), (3600, 5), (86400, 10))  # (seconds, sends)


async def code_send_wait(kind: str, ident: str, *, exempt: bool = False) -> int:
    """0 if a code may be sent to ``ident`` now (and the send is counted), else the seconds
    to wait. ``exempt``: the seed's fictional numbers and @example.com outside production
    (they always get the fixed code, so nothing is sent to a real person)."""
    if exempt:
        return 0
    redis = await get_redis()
    h = ident_hash(ident)
    keys = [f"rl:{kind}:{window}:{h}" for window, _ in CODE_SEND_WINDOWS]
    counts = await redis.mget(keys)
    for (window, limit), key, count in zip(CODE_SEND_WINDOWS, keys, counts):
        if count is not None and int(count) >= limit:
            return max(1, int(await redis.ttl(key) or window))
    for (window, _), key in zip(CODE_SEND_WINDOWS, keys):
        if await redis.incr(key) == 1:
            await redis.expire(key, window)
    return 0


def too_many_codes(wait: int, what: str = "number"):  # type: ignore[no-untyped-def]
    """429 TOO_MANY_CODES with retry_after (seconds); the clients say "Try again in N s"."""
    from fastapi import HTTPException, status

    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "TOO_MANY_CODES", "message": f"Too many codes for this {what}. Try again in {wait} seconds.",
                "retry_after": wait},
        headers={"Retry-After": str(wait)},
    )
