"""Email: log, SMTP (Mailpit locally), SendGrid or Amazon SES (production, R19)."""
import asyncio
from email.message import EmailMessage
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError, refuse_in_production

logger = structlog.get_logger(__name__)


class EmailProvider(Protocol):
    name: str

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool: ...


def _sender() -> tuple[str, str]:
    w = get_settings().worker
    return w.EMAIL_FROM or w.SENDGRID_FROM_EMAIL, w.EMAIL_FROM_NAME or w.SENDGRID_FROM_NAME


class LogEmail:
    name = "log"

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        logger.info("email_local", to=to, subject=subject)
        return True


class SmtpEmail:
    """Plain SMTP. Locally this is Mailpit: read the mail at http://localhost:8025."""

    name = "smtp"

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        import aiosmtplib

        p = get_settings().providers
        from_email, from_name = _sender()
        msg = EmailMessage()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text or "This email needs an HTML-capable mail client.")
        msg.add_alternative(html, subtype="html")
        try:
            await aiosmtplib.send(msg, hostname=p.SMTP_HOST, port=p.SMTP_PORT, timeout=10)
            logger.info("email_sent", provider="smtp", to=to, subject=subject)
            return True
        except Exception as e:  # noqa: BLE001 - report it, don't crash the worker
            logger.error("email_send_failed", provider="smtp", to=to, error=str(e))
            return False


class SendGridEmail:
    name = "sendgrid"

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        from_email, from_name = _sender()
        try:
            r = SendGridAPIClient(get_settings().worker.SENDGRID_API_KEY).send(
                Mail(from_email=(from_email, from_name), to_emails=to, subject=subject, html_content=html,
                     plain_text_content=text or None)
            )
            return r.status_code in (200, 201, 202)
        except Exception as e:  # noqa: BLE001
            logger.error("email_send_failed", provider="sendgrid", to=to, error=str(e))
            return False


class SesEmail:
    """Amazon SES through the SES v2 API (boto3's ``sesv2`` client, SigV4 signed by boto3).

    Settings (worker): SES_REGION, SES_ACCESS_KEY_ID, SES_SECRET_ACCESS_KEY (an IAM user allowed
    ses:SendEmail only), EMAIL_FROM / EMAIL_FROM_NAME (an address on the domain verified in SES,
    with DKIM), SES_CONFIGURATION_SET (optional). docs/launch/go-live.md has the set-up.
    """

    name = "ses"

    def __init__(self, client=None) -> None:  # type: ignore[no-untyped-def]
        self._client = client

    def client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            import boto3

            w = get_settings().worker
            self._client = boto3.client("sesv2", region_name=w.SES_REGION, aws_access_key_id=w.SES_ACCESS_KEY_ID,
                                        aws_secret_access_key=w.SES_SECRET_ACCESS_KEY)
        return self._client

    def request(self, to: str, subject: str, html: str, text: str = "") -> dict:
        from email.utils import formataddr

        from_email, from_name = _sender()
        body: dict = {"Html": {"Data": html, "Charset": "UTF-8"}}
        if text:
            body["Text"] = {"Data": text, "Charset": "UTF-8"}
        req: dict = {
            "FromEmailAddress": formataddr((from_name, from_email)) if from_name else from_email,
            "Destination": {"ToAddresses": [to]},
            "Content": {"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body}},
        }
        config_set = get_settings().worker.SES_CONFIGURATION_SET
        if config_set:
            req["ConfigurationSetName"] = config_set
        return req

    async def send(self, to: str, subject: str, html: str, text: str = "") -> bool:
        try:
            r = await asyncio.to_thread(lambda: self.client().send_email(**self.request(to, subject, html, text)))
            logger.info("email_sent", provider="ses", message_id=r.get("MessageId"))
            return True
        except Exception as e:  # noqa: BLE001 - botocore ClientError, credentials, network: report, don't crash
            logger.error("email_send_failed", provider="ses", error=str(e))
            return False


def get_email_provider() -> EmailProvider:
    name = get_settings().providers.EMAIL_PROVIDER
    if name == "log":
        refuse_in_production("Email", name)
        return LogEmail()
    if name == "smtp":
        return SmtpEmail()
    if name == "sendgrid":
        return SendGridEmail()
    if name == "ses":
        return SesEmail()
    raise ProviderConfigError(f"Unknown EMAIL_PROVIDER '{name}'")
