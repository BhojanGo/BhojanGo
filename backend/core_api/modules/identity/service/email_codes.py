"""Six-digit codes sent by email: verifying a new account's address, signing in
without a password, linking an email, confirming a two-step enrolment.

Each code belongs to one purpose and one address, lives OTP_EXPIRE_MINUTES, is
stored as a SHA-256 hash, allows MAX_ATTEMPTS wrong tries (then it is burnt) and
is used up when it works. Outside production, addresses in
OTP_FIXED_CODE_EMAIL_DOMAINS (the seed and the tests use @example.com) get
OTP_FIXED_CODE, like the seed phones; never in production.

  email_code:{purpose}:{hash}           sha256 of the code   (TTL)
  email_code_tries:{purpose}:{hash}     wrong tries          (TTL)
"""
import hashlib
import hmac

from core_api.modules.identity.service.guard import ident_hash
from core_api.modules.identity.service.security import generate_otp
from shared.config import get_settings
from shared.redis import get_redis

MAX_ATTEMPTS = 5


def _digest(code: str) -> str:
    return hashlib.sha256(code.encode("ascii", "ignore")).hexdigest()


def fixed_code_for(email: str) -> str | None:
    s = get_settings()
    p = s.providers
    if s.is_production or s.production_named or not p.OTP_FIXED_CODE:
        return None
    domain = email.strip().lower().rsplit("@", 1)[-1]
    return p.OTP_FIXED_CODE if domain in {d.lower() for d in p.OTP_FIXED_CODE_EMAIL_DOMAINS} else None


def ttl_minutes() -> int:
    return get_settings().identity.OTP_EXPIRE_MINUTES


async def issue(purpose: str, email: str) -> str:
    code = fixed_code_for(email) or generate_otp(6)
    h = ident_hash(email)
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.setex(f"email_code:{purpose}:{h}", ttl_minutes() * 60, _digest(code))
    pipe.delete(f"email_code_tries:{purpose}:{h}")
    await pipe.execute()
    return code


async def check(purpose: str, email: str, code: str) -> bool:
    """True (and the code is used up) if ``code`` is the live code for ``email``."""
    h = ident_hash(email)
    redis = await get_redis()
    stored = await redis.get(f"email_code:{purpose}:{h}")
    if stored is None:
        return False
    if not hmac.compare_digest(stored, _digest((code or "").strip())):
        tries = await redis.incr(f"email_code_tries:{purpose}:{h}")
        if tries == 1:
            await redis.expire(f"email_code_tries:{purpose}:{h}", ttl_minutes() * 60)
        if tries >= MAX_ATTEMPTS:
            await redis.delete(f"email_code:{purpose}:{h}", f"email_code_tries:{purpose}:{h}")
        return False
    await redis.delete(f"email_code:{purpose}:{h}", f"email_code_tries:{purpose}:{h}")
    return True
