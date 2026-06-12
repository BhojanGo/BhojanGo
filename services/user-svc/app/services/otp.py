import structlog
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import get_settings
from app.core.redis import get_redis, otp_attempts_key, otp_key
from app.core.security import generate_otp

logger = structlog.get_logger(__name__)
settings = get_settings()

MAX_OTP_ATTEMPTS = 5


async def send_otp(phone: str, country: str) -> bool:
    """Generate OTP, store in Redis, send via Twilio. Returns True on success."""
    redis = await get_redis()

    # Check attempts
    attempts_key = otp_attempts_key(phone)
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= MAX_OTP_ATTEMPTS:
        logger.warning("otp_max_attempts_reached", phone=phone)
        return False

    otp = generate_otp(settings.OTP_LENGTH)
    ttl_seconds = settings.OTP_EXPIRE_MINUTES * 60

    # Store OTP
    await redis.setex(otp_key(phone), ttl_seconds, otp)

    # Increment attempts
    pipe = redis.pipeline()
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, ttl_seconds)
    await pipe.execute()

    # Send via Twilio
    if not settings.TWILIO_ACCOUNT_SID or settings.APP_ENV == "test":
        # Only expose the OTP value for local dev/test convenience — NEVER log secrets otherwise.
        if settings.APP_ENV in ("development", "test"):
            logger.info("otp_mock_send", phone=phone[-4:], otp=otp)
        else:
            logger.warning("otp_mock_send_no_provider", phone=phone[-4:])
        return True

    try:
        from_number = settings.TWILIO_PHONE_NUMBER_IN if country == "IN" else settings.TWILIO_PHONE_NUMBER
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"Your BhojanGo verification code is: {otp}. Valid for {settings.OTP_EXPIRE_MINUTES} minutes.",
            from_=from_number,
            to=phone,
        )
        logger.info("otp_sent", phone=phone[-4:])
        return True
    except TwilioRestException as e:
        logger.error("otp_send_failed", phone=phone[-4:], error=str(e))
        return False


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
