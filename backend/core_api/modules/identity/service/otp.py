import structlog
from shared import notify
from shared.config import get_settings
from core_api.modules.identity.service.redis_keys import otp_attempts_key, otp_key
from shared.redis import get_redis
from core_api.modules.identity.service.security import generate_otp

logger = structlog.get_logger(__name__)
settings = get_settings()

MAX_OTP_ATTEMPTS = 5


async def send_otp(phone: str, country: str) -> bool:
    """Generate an OTP, store it in Redis and have the worker text it. True on success."""
    redis = await get_redis()

    # Check attempts
    attempts_key = otp_attempts_key(phone)
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= MAX_OTP_ATTEMPTS:
        logger.warning("otp_max_attempts_reached", phone=phone)
        return False

    otp = _fixed_code_for(phone) or generate_otp(settings.identity.OTP_LENGTH)
    ttl_seconds = settings.identity.OTP_EXPIRE_MINUTES * 60

    # Store OTP
    await redis.setex(otp_key(phone), ttl_seconds, otp)

    # Increment attempts
    pipe = redis.pipeline()
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, ttl_seconds)
    await pipe.execute()

    # The worker sends it (locally: printed in the worker log).
    body = f"Your BhojanGo verification code is: {otp}. Valid for {settings.identity.OTP_EXPIRE_MINUTES} minutes."
    return await notify.send("sms", phone, body, country=country)


def _fixed_code_for(phone: str) -> str | None:
    """Seed users get a fixed code outside production, so local sign-in needs no SMS."""
    p = settings.providers
    if settings.is_production or not p.OTP_FIXED_CODE:
        return None
    return p.OTP_FIXED_CODE if any(phone.startswith(x) for x in p.OTP_FIXED_CODE_PHONE_PREFIXES) else None


async def verify_otp(phone: str, otp: str) -> bool:
    """Returns True if OTP matches and is still valid."""
    redis = await get_redis()
    stored_otp = await redis.get(otp_key(phone))

    if stored_otp is None:
        logger.info("otp_expired_or_not_found", phone=phone[-4:])
        return False

    if stored_otp != otp:
        logger.info("otp_mismatch", phone=phone[-4:])
        return False

    # Consume OTP — delete after successful verification
    await redis.delete(otp_key(phone))
    await redis.delete(otp_attempts_key(phone))
    return True
