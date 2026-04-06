"""SendGrid email notifications."""
import structlog
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


async def send_email(to_email: str, subject: str, html_content: str) -> bool:
    if not settings.SENDGRID_API_KEY or settings.APP_ENV in ("test", "development"):
        logger.info("email_mock_send", to=to_email, subject=subject)
        return True

    message = Mail(
        from_email=(settings.SENDGRID_FROM_EMAIL, settings.SENDGRID_FROM_NAME),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info("email_sent", to=to_email, status=response.status_code)
        return response.status_code in (200, 201, 202)
    except Exception as e:
        logger.error("email_send_failed", to=to_email, error=str(e))
        return False


def order_confirmation_html(order_id: str, items: list[dict], total: float, currency: str) -> str:
    currency_symbol = "$" if currency == "USD" else "₹"
    items_html = "".join(f"<tr><td>{i.get('name','Item')}</td><td>{i.get('quantity',1)}</td><td>{currency_symbol}{i.get('price',0):.2f}</td></tr>" for i in items)
    return f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #f97316; padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">BhojanGo</h1>
      </div>
      <div style="padding: 20px;">
        <h2>Order Confirmed! 🎉</h2>
        <p>Your order <strong>#{order_id[:8].upper()}</strong> has been confirmed.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
          <thead><tr style="background: #f3f4f6;">
            <th style="padding: 8px; text-align: left;">Item</th>
            <th>Qty</th><th>Price</th>
          </tr></thead>
          <tbody>{items_html}</tbody>
          <tfoot><tr style="font-weight: bold;">
            <td colspan="2" style="padding: 8px;">Total</td>
            <td>{currency_symbol}{total:.2f}</td>
          </tr></tfoot>
        </table>
        <p style="color: #6b7280; font-size: 14px;">Track your order in the BhojanGo app.</p>
      </div>
    </body></html>
    """
