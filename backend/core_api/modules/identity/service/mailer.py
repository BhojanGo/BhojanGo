"""The sign-in emails (texts in shared/texts.py AUTH_EMAILS, sent by the worker's
email provider through shared/notify: Mailpit or the log locally)."""
import html

from shared import notify
from shared.config import get_settings
from shared.texts import AUTH_EMAILS, LANGUAGES, WELCOME, pick


def language(lang: str | None, fallback_locale: str | None = None) -> str:
    if lang and lang in LANGUAGES:
        return lang
    base = (fallback_locale or "en").split("-")[0].lower()
    return base if base in LANGUAGES else "en"


def web_link(path: str) -> str:
    return get_settings().identity.PUBLIC_WEB_URL.rstrip("/") + path


def _html(body: str, link: str | None) -> str:
    text = html.escape(body)
    if link:
        safe = html.escape(link, quote=True)
        text = text.replace(html.escape(link), f'<a href="{safe}">{safe}</a>')
    return (f'<div style="font-family:Inter,Arial,sans-serif;font-size:16px;line-height:1.5;color:#0B1F24">'
            f"<p>{text}</p><p>BhojanGo</p></div>")


async def send(to: str, kind: str, lang: str, **values: str | int) -> bool:
    """kind: code | exists | reset | changed | email_replaced."""
    subject = pick(AUTH_EMAILS[f"{kind}.subject"], lang).format(**values)
    body = pick(AUTH_EMAILS[f"{kind}.body"], lang).format(**values)
    link = values.get("link")
    return await notify.send("email", to, _html(body, str(link) if link else None), subject=subject)


async def send_code(to: str, code: str, lang: str, minutes: int) -> bool:
    return await send(to, "code", lang, code=code, minutes=minutes)


async def send_welcome(to: str, name: str, lang: str) -> bool:
    """The welcome email after a new account's email is verified (shared/texts.py WELCOME)."""
    first = (name or "").strip()
    hello = pick(WELCOME["hello"], lang).format(name=html.escape(first)) if first else pick(WELCOME["hello_anon"], lang)
    body = (f"<p>{hello}</p><p>{html.escape(pick(WELCOME['body'], lang))}</p>"
            f"<p>{html.escape(pick(WELCOME['signoff'], lang))}</p>")
    return await notify.send("email", to, body, subject=pick(WELCOME["subject"], lang))
