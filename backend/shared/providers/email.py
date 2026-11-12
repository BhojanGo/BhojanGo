"""Email: log, SMTP (Mailpit locally) or SendGrid."""
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
    return w.SENDGRID_FROM_EMAIL, w.SENDGRID_FROM_NAME


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


def get_email_provider() -> EmailProvider:
    name = get_settings().providers.EMAIL_PROVIDER
    if name == "log":
        refuse_in_production("Email", name)
        return LogEmail()
    if name == "smtp":
        return SmtpEmail()
    if name == "sendgrid":
        return SendGridEmail()
    raise ProviderConfigError(f"Unknown EMAIL_PROVIDER '{name}'")
