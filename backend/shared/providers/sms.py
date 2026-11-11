"""SMS: log (local), or live: Twilio for the US and MSG91 for India.

India requires DLT-registered templates for every SMS, so messages carry a
template key and its variables as well as the rendered text. Twilio sends the
text; MSG91 sends the template id mapped from the key (MSG91_TEMPLATE_IDS)
with the variables. The log provider prints the text.
"""
from typing import Protocol

import httpx
import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError, refuse_in_production

logger = structlog.get_logger(__name__)


class SmsProvider(Protocol):
    name: str

    async def send(self, to: str, body: str, country: str, template: str = "", params: dict | None = None) -> bool: ...


class LogSms:
    """Prints the message to the service log (local development and tests)."""

    name = "log"

    async def send(self, to: str, body: str, country: str, template: str = "", params: dict | None = None) -> bool:
        logger.info("sms_local", to=to, country=country, template=template, body=body)
        print(f"[SMS to {to}] {body}", flush=True)  # easy to spot in `make logs`
        return True


class TwilioSms:
    name = "twilio"

    async def send(self, to: str, body: str, country: str, template: str = "", params: dict | None = None) -> bool:
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


class Msg91Sms:
    """MSG91 Flow API with a DLT template (India)."""

    name = "msg91"
    URL = "https://control.msg91.com/api/v5/flow"

    async def send(self, to: str, body: str, country: str, template: str = "", params: dict | None = None) -> bool:
        p = get_settings().providers
        template_id = p.MSG91_TEMPLATE_IDS.get(template)
        if not template_id:
            logger.error("sms_send_failed", provider="msg91", reason=f"no DLT template for {template!r}")
            return False
        recipient = {"mobiles": to.lstrip("+"), **{k: str(v) for k, v in (params or {}).items()}}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    self.URL,
                    headers={"authkey": p.MSG91_AUTH_KEY, "content-type": "application/json"},
                    json={"template_id": template_id, "short_url": "0", "recipients": [recipient]},
                )
            ok = r.status_code == 200 and r.json().get("type") == "success"
            logger.info("sms_sent" if ok else "sms_send_failed", provider="msg91", to=to[-4:], status=r.status_code)
            return ok
        except httpx.HTTPError as e:
            logger.error("sms_send_failed", provider="msg91", to=to[-4:], error=str(e))
            return False


def get_sms_provider(country: str = "US") -> SmsProvider:
    name = get_settings().providers.SMS_PROVIDER
    if name == "log":
        refuse_in_production("SMS", name)
        return LogSms()
    if name == "live":
        return Msg91Sms() if country == "IN" else TwilioSms()
    if name == "twilio":
        return TwilioSms()
    raise ProviderConfigError(f"Unknown SMS_PROVIDER '{name}' (log | live)")
