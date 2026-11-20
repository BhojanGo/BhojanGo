"""A signed-in website session for a Playwright browser, without the sign-in screens.

Since R22 (security review S8) the website's session is two httpOnly cookies on the
API's host (bg_web_at, bg_web_rt; backend/shared/session.py) and the page keeps only
who is signed in (localStorage "bhojango-session-v2"). The scripts sign in through the
API like an app (tokens in the answer) and hand the browser the same session.
"""
import json
from urllib.parse import urlsplit


def cookies(core_url: str, access_token: str, refresh_token: str) -> list[dict]:
    """The session's cookies for ctx.add_cookies, on core_api's host."""
    parts = urlsplit(core_url)
    origin = f"{parts.scheme}://{parts.netloc}"
    secure = parts.scheme == "https"  # http://localhost works without (the API sets Secure; a browser keeps it there too)
    return [{"name": name, "value": value, "url": origin, "httpOnly": True, "secure": secure, "sameSite": "Lax"}
            for name, value in (("bg_web_at", access_token), ("bg_web_rt", refresh_token))]


def script(user: dict) -> str:
    """An init script that tells the page who is signed in (no token in it)."""
    state = json.dumps({"state": {"signedIn": True, "user": user}, "version": 0})
    return f"if (!localStorage.getItem('bhojango-session-v2')) localStorage.setItem('bhojango-session-v2', {json.dumps(state)});"
