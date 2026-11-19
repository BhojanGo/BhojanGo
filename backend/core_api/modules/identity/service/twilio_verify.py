"""Phone sign-in codes through Twilio Verify (OTP_PROVIDER=twilio_verify; production, R19).

Verify makes, sends and checks the code itself, from Twilio's own numbers, so no sender
number or A2P 10DLC registration is needed and we never see or store the code. Two calls
(the Verify v2 REST API, basic auth with the account SID and auth token):

  POST https://verify.twilio.com/v2/Services/{service}/Verifications       To, Channel=sms[, Locale]
  POST https://verify.twilio.com/v2/Services/{service}/VerificationCheck   To, Code   -> status "approved"

Settings (core_api): TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID.
Our own per-number send limits (guard.code_send_wait) still apply first; Verify adds its
own (5 sends per number per 10 minutes, 5 checks per code).
"""
from __future__ import annotations

import httpx
import structlog

from shared.config import get_settings

logger = structlog.get_logger(__name__)

BASE = "https://verify.twilio.com/v2/Services"
# Languages Verify's SMS template is used in; others get Verify's default for the number's country.
LOCALES = {"en", "es", "hi"}


class TooManyCodes(Exception):
    """Verify refused to send another code to this number for now (HTTP 429, error 60203)."""


def _client(client: httpx.AsyncClient | None) -> httpx.AsyncClient:
    i = get_settings().identity
    return client or httpx.AsyncClient(timeout=10, auth=(i.TWILIO_ACCOUNT_SID, i.TWILIO_AUTH_TOKEN))


def _url(path: str) -> str:
    return f"{BASE}/{get_settings().identity.TWILIO_VERIFY_SERVICE_SID}/{path}"


async def start(phone: str, language: str = "en", *, client: httpx.AsyncClient | None = None) -> bool:
    """Ask Verify to text a new code to ``phone``. True when Verify accepted it."""
    form = {"To": phone, "Channel": "sms", **({"Locale": language} if language in LOCALES else {})}
    try:
        async with _client(client) as c:
            r = await c.post(_url("Verifications"), data=form)
    except httpx.HTTPError as e:
        logger.error("verify_start_failed", phone=phone[-4:], error=str(e))
        return False
    if r.status_code == 429:
        raise TooManyCodes()
    ok = r.status_code in (200, 201) and r.json().get("status") == "pending"
    if not ok:
        logger.error("verify_start_failed", phone=phone[-4:], status=r.status_code, code=_error_code(r))
    return ok


async def check(phone: str, code: str, *, client: httpx.AsyncClient | None = None) -> bool:
    """True when ``code`` is the live code Verify sent to ``phone`` (Verify then marks it used)."""
    code = (code or "").strip()
    if not code.isdigit():
        return False
    try:
        async with _client(client) as c:
            r = await c.post(_url("VerificationCheck"), data={"To": phone, "Code": code})
    except httpx.HTTPError as e:
        logger.error("verify_check_failed", phone=phone[-4:], error=str(e))
        return False
    if r.status_code == 404:  # no pending code: expired, used, or too many wrong tries
        logger.info("otp_expired_or_not_found", phone=phone[-4:], provider="twilio_verify")
        return False
    if r.status_code != 200:
        logger.error("verify_check_failed", phone=phone[-4:], status=r.status_code, code=_error_code(r))
        return False
    return r.json().get("status") == "approved"


def _error_code(r: httpx.Response) -> object:
    try:
        return r.json().get("code")
    except ValueError:
        return None
