"""Browser sessions in cookies (R22 security review, S8).

The website and the admin console used to keep the access and refresh tokens
in localStorage, where any script on the page could read them. Now:

* A browser client says which one it is with the ``X-Session: web|admin``
  header. core_api then answers every sign-in, refresh and sign-up that issues
  tokens with two cookies instead of tokens in the body (the body's
  ``access_token`` and ``refresh_token`` become ""):

    bg_<client>_at  the access token   HttpOnly; Secure; SameSite=Lax; Path=/
    bg_<client>_rt  the refresh token  HttpOnly; Secure; SameSite=Lax; Path=/

  Both cookies last as long as the refresh token (7 days). The access token in
  the cookie still expires after 15 minutes: the browser keeps sending it, the
  API answers 401, and the page refreshes the session (as the apps do).

  No Domain attribute: each cookie belongs to the one host that set it. The
  website calls core_api directly (api.<site>, same site as the website), so
  its cookies live on the API's host. The console calls core_api through its
  own /api rewrites, so its cookies live on the console's host. The two names
  differ so both work side by side on localhost, where ports share cookies.

* A request authenticates with ``Authorization: Bearer`` (the apps, scripts,
  tests: unchanged) or, when there is no such header, with the cookie named
  by its ``X-Session`` header. A read (GET, HEAD) without the header may use
  the website's cookie: that keeps the website's reads "simple" requests (no
  CORS preflight before each one). A read changes nothing, another site can't
  read the answer (CORS), and SameSite=Lax keeps the cookie off other sites'
  images, scripts and frames.

* CSRF: a state-changing request (anything but GET, HEAD, OPTIONS) uses a
  cookie only with the ``X-Session`` header, and only from one of our own
  origins (``Origin``, else ``Referer``, in CORS_ORIGINS). ``X-Session`` is a
  custom header, so another site's page can't send it without a CORS
  preflight, which only our origins pass. Refused: 403 ``CSRF``.

* The realtime WebSocket (rt.<site>) can't see the API's cookies: the website
  asks core_api for a socket ticket (POST /auth/socket-ticket, a JWT of type
  ``ws`` that expires with the session's access token) and opens the socket
  with it. Only WebSockets accept a ticket; every HTTP route refuses one.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shared.config import get_settings

HEADER = "x-session"
CLIENTS = frozenset({"web", "admin"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Paths (under /api/v1) whose answers end a browser session: its cookies are cleared whatever the status.
SIGN_OUT_PATHS = ("/api/v1/auth/logout",)


def access_cookie(client: str) -> str:
    return f"bg_{client}_at"


def refresh_cookie(client: str) -> str:
    return f"bg_{client}_rt"


def client_of(conn: HTTPConnection | Scope) -> str | None:
    """"web" or "admin" when a browser client says so (X-Session), else None."""
    headers = conn.headers if isinstance(conn, HTTPConnection) else HTTPConnection(conn).headers
    value = headers.get(HEADER, "").strip().lower()
    return value if value in CLIENTS else None


def _origin(value: str) -> str:
    parts = urlsplit(value)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def trusted_origins() -> set[str]:
    return {o.rstrip("/") for o in get_settings().CORS_ORIGINS if o and o != "*"}


def check_origin(conn: HTTPConnection) -> None:
    """403 CSRF unless the request comes from one of our own origins."""
    origin = conn.headers.get("origin") or _origin(conn.headers.get("referer", ""))
    if not origin or origin.rstrip("/") not in trusted_origins():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"code": "CSRF", "message": "This request didn't come from a BhojanGo page"})


def cookie_token(conn: HTTPConnection, kind: str = "access") -> str | None:
    """The session cookie's token for a browser client's HTTP request, after the CSRF check
    when the request changes something. None when there is no client header or no cookie."""
    if conn.scope.get("type") != "http":
        return None  # WebSockets take a socket ticket, never a cookie
    safe = conn.scope.get("method", "GET").upper() in SAFE_METHODS
    client = client_of(conn) or ("web" if safe else None)  # a change always names its client
    if client is None:
        return None
    token = conn.cookies.get(access_cookie(client) if kind == "access" else refresh_cookie(client))
    if not token:
        return None
    if not safe:
        check_origin(conn)
    return token


def _cookie(name: str, value: str, max_age: int) -> str:
    # Secure: browsers keep it on https, and on http://localhost (a secure context) for local runs.
    return f"{name}={value}; Max-Age={max_age}; Path=/; HttpOnly; Secure; SameSite=Lax"


def set_cookie_headers(client: str, access: str, refresh: str) -> list[str]:
    # Both live as long as the session: an expired access token is still sent, so the API
    # answers 401 and the page refreshes (instead of a missing cookie's 403).
    days = get_settings().identity.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    return [_cookie(access_cookie(client), access, days * 86400),
            _cookie(refresh_cookie(client), refresh, days * 86400)]


def clear_cookie_headers(client: str) -> list[str]:
    return [_cookie(access_cookie(client), "", 0), _cookie(refresh_cookie(client), "", 0)]


class SessionCookieMiddleware:
    """core_api: turns the tokens in a browser client's sign-in answers into cookies, and
    clears them on sign-out or a failed refresh. Answers to the apps (no X-Session) pass
    through untouched. Only POST answers that are JSON are read (every token issuer is a POST)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST" or client_of(scope) is None:
            await self.app(scope, receive, send)
            return
        client = client_of(scope) or ""
        path = scope.get("path", "")
        start: Message | None = None
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
                return
            if message["type"] != "http.response.body":
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            assert start is not None
            body = b"".join(chunks)
            headers = MutableHeaders(scope=start)
            cookies: list[str] = []
            if path in SIGN_OUT_PATHS or (path == "/api/v1/auth/refresh" and start["status"] == 401):
                cookies = clear_cookie_headers(client)
            elif 200 <= start["status"] < 300 and headers.get("content-type", "").startswith("application/json"):
                body, cookies = _move_tokens(client, body)
            for c in cookies:
                headers.append("set-cookie", c)
            if cookies:
                headers["content-length"] = str(len(body))
                headers["cache-control"] = "no-store"
            await send(start)
            await send({"type": "http.response.body", "body": body, "more_body": False})

        await self.app(scope, receive, capture)


def _move_tokens(client: str, body: bytes) -> tuple[bytes, list[str]]:
    try:
        data: Any = json.loads(body)
    except ValueError:
        return body, []
    if not isinstance(data, dict):
        return body, []
    access, refresh = data.get("access_token"), data.get("refresh_token")
    if not (isinstance(access, str) and access and isinstance(refresh, str) and refresh):
        return body, []
    data["access_token"], data["refresh_token"] = "", ""
    return json.dumps(data, separators=(",", ":")).encode(), set_cookie_headers(client, access, refresh)
