"""SMS: log (local) or Twilio."""
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError, refuse_in_production

logger = structlog.get_logger(__name__)


class SmsProvider(Protocol):
    name: str

    async def send(self, to: str, body: str, country: str) -> bool: ...


class LogSms:
    """Prints the message to the service log (local development and tests)."""

    name = "log"

    async def send(self, to: str, body: str, country: str) -> bool:
        logger.info("sms_local", to=to, country=country, body=body)
        print(f"[SMS to {to}] {body}", flush=True)  # easy to spot in `make logs`
        return True


class TwilioSms:
    name = "twilio"

    async def send(self, to: str, body: str, country: str) -> bool:
        from twilio.base.exceptions import TwilioRestException
        from twilio.rest import Client

        w = get_settings().worker
        from_number = w.TWILIO_PHONE_NUMBER_IN if country == "IN" else w.TWILIO_PHONE_NUMBER
        try:
            Client(w.TWILIO_ACCOUNT_SID, w.TWILIO_AUTH_TOKEN).messages.create(body=body, from_=from_number, to=to)
            logger.info("sms_sent", provider="twilio", to=to[-4:])
            return True
        except TwilioRestException as e:
            logger.error("sms_send_failed", provider="twilio", to=to[-4:], error=str(e))
            return False


def get_sms_provider() -> SmsProvider:
    name = get_settings().providers.SMS_PROVIDER
    if name == "log":
        refuse_in_production("SMS", name)
        return LogSms()
    if name == "twilio":
        return TwilioSms()
    raise ProviderConfigError(f"Unknown SMS_PROVIDER '{name}'")
