"""Twilio SMS for order update notifications."""
import structlog
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


async def send_sms(phone: str, message: str, country: str = "US") -> bool:
    if not settings.TWILIO_ACCOUNT_SID or settings.APP_ENV in ("test", "development"):
        logger.info("sms_mock_send", phone=phone[-4:], message=message[:50])
        return True

    from_number = settings.TWILIO_PHONE_NUMBER_IN if country == "IN" else settings.TWILIO_PHONE_NUMBER
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(body=message, from_=from_number, to=phone)
        logger.info("sms_sent", phone=phone[-4:])
        return True
    except TwilioRestException as e:
        logger.error("sms_send_failed", phone=phone[-4:], error=str(e))
        return False
