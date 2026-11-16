"""SMS sign-in codes.

Sending is limited per phone number (service/guard.py code_send_wait: 1 per 30 s,
5 per hour, 10 per day), not per IP: many people share an IP behind carrier-grade NAT.
A code allows MAX_WRONG_TRIES wrong tries, then it is burnt (ask for a new one).
"""
import hmac

import structlog

from core_api.modules.identity.service import guard
from core_api.modules.identity.service.redis_keys import otp_attempts_key, otp_key
from core_api.modules.identity.service.security import generate_otp
from shared import notify
from shared.config import get_settings
from shared.redis import get_redis
from shared.texts import OTP_SMS, pick

logger = structlog.get_logger(__name__)
settings = get_settings()

MAX_WRONG_TRIES = 5


async def send_otp(phone: str, country: str, language: str = "en") -> bool:
    """Generate a code, store it in Redis and have the worker text it in ``language``
    (shared/texts.py OTP_SMS; India's DLT template key is "otp_<language>"). True when
    handed to the SMS provider; raises 429 TOO_MANY_CODES (guard.too_many_codes) when
    this number had too many codes lately."""
    fixed = _fixed_code_for(phone)
    wait = await guard.code_send_wait("sms", phone, exempt=bool(fixed))
    if wait:
        logger.info("otp_send_limited", phone=phone[-4:], wait=wait)
        raise guard.too_many_codes(wait, "number")

    otp = fixed or generate_otp(settings.identity.OTP_LENGTH)
    ttl_seconds = settings.identity.OTP_EXPIRE_MINUTES * 60
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.setex(otp_key(phone), ttl_seconds, otp)
    pipe.delete(otp_attempts_key(phone))  # a new code: its own wrong tries
    await pipe.execute()

    # The worker sends it (locally: printed in the worker log).
    minutes = settings.identity.OTP_EXPIRE_MINUTES
    language = language if language in OTP_SMS else "en"
    body = pick(OTP_SMS, language).format(otp=otp, minutes=minutes)
    return await notify.send("sms", phone, body, country=country, template=f"otp_{language}",
                             params={"otp": otp, "minutes": minutes})


def _fixed_code_for(phone: str) -> str | None:
    """Seed users get a fixed code outside production, so local sign-in needs no SMS."""
    p = settings.providers
    if settings.is_production or not p.OTP_FIXED_CODE:
        return None
    return p.OTP_FIXED_CODE if any(phone.startswith(x) for x in p.OTP_FIXED_CODE_PHONE_PREFIXES) else None


async def verify_otp(phone: str, otp: str) -> bool:
    """True if ``otp`` is the live code for ``phone`` (and it is used up). Wrong tries
    count; after MAX_WRONG_TRIES the code is burnt."""
    redis = await get_redis()
    stored_otp = await redis.get(otp_key(phone))

    if stored_otp is None:
        logger.info("otp_expired_or_not_found", phone=phone[-4:])
        return False

    if not hmac.compare_digest(stored_otp, otp or ""):
        tries = await redis.incr(otp_attempts_key(phone))
        if tries == 1:
            await redis.expire(otp_attempts_key(phone), settings.identity.OTP_EXPIRE_MINUTES * 60)
        if tries >= MAX_WRONG_TRIES:
            await redis.delete(otp_key(phone), otp_attempts_key(phone))
            logger.info("otp_burnt_after_wrong_tries", phone=phone[-4:])
        else:
            logger.info("otp_mismatch", phone=phone[-4:])
        return False

    # Consume OTP — delete after successful verification
    await redis.delete(otp_key(phone), otp_attempts_key(phone))
    return True
