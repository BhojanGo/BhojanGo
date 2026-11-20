"""R22 security review, S8 (docs/launch/security-review.md): the website's and the console's
sessions live in httpOnly cookies, never in the page; a cookie counts only with the client's
X-Session header, and a request that changes something must come from our own origin (CSRF).
The apps' bearer tokens work as before. Each test fails without the fix.

A small app with the real middleware and the real BearerAuth; the integration test
(core_api/integration/test_security_review_r22.py) runs the same through real sign-ins.
"""
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient

from shared.auth import BearerAuth
from shared.config import get_settings

OURS = "http://localhost:3000"


@pytest.fixture
async def client(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "CORS_ORIGINS", [OURS, "http://localhost:3001"])
    app = FastAPI()
    try:
        from shared.session import SessionCookieMiddleware

        app.add_middleware(SessionCookieMiddleware)
    except ImportError:  # before the fix: the app as it was, so each test fails on what it checks
        pass
    security = BearerAuth()

    @app.post("/api/v1/auth/login")
    async def login() -> dict:
        return {"access_token": "AT", "refresh_token": "RT", "token_type": "bearer", "expires_in": 900, "user": {"id": "u"}}

    @app.post("/api/v1/auth/logout")
    async def logout(c: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> dict:
        return {"message": "bye"}

    @app.get("/api/v1/me")
    async def me(c: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> dict:
        return {"token": c.credentials}

    @app.post("/api/v1/me")
    async def change(c: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> dict:
        return {"token": c.credentials}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def set_cookies(r) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {c.split("=", 1)[0]: c for c in r.headers.get_list("set-cookie")}


async def test_a_browser_sign_in_gets_httponly_cookies_and_no_tokens(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/login", headers={"X-Session": "admin", "Origin": "http://localhost:3001"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "" and body["refresh_token"] == "", body  # nothing for a script to read
    assert body["user"] == {"id": "u"}
    cookies = set_cookies(r)
    for name, value in (("bg_admin_at", "AT"), ("bg_admin_rt", "RT")):
        c = cookies[name]
        assert c.startswith(f"{name}={value};"), c
        for attr in ("HttpOnly", "Secure", "SameSite=Lax", "Path=/"):
            assert attr in c, c
        assert "Domain" not in c, c  # only the host that set it
    week = f"Max-Age={7 * 86400}"
    assert week in cookies["bg_admin_at"] and week in cookies["bg_admin_rt"]  # an expired token is still sent: 401, refresh
    assert r.headers["cache-control"] == "no-store"


async def test_the_apps_still_get_their_tokens(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/login")
    assert r.json()["access_token"] == "AT" and r.json()["refresh_token"] == "RT"
    assert not r.headers.get_list("set-cookie")


async def test_a_cookie_counts_only_for_its_client(client: AsyncClient) -> None:
    jar = {"Cookie": "bg_web_at=AT"}
    assert (await client.get("/api/v1/me", headers={**jar, "X-Session": "web"})).json() == {"token": "AT"}
    # The website's reads go without the header (no CORS preflight before each); they change nothing.
    assert (await client.get("/api/v1/me", headers=jar)).json() == {"token": "AT"}
    assert (await client.get("/api/v1/me", headers={**jar, "X-Session": "admin"})).status_code == 401  # the other client's name
    # The console's cookie needs the console's header.
    assert (await client.get("/api/v1/me", headers={"Cookie": "bg_admin_at=AD"})).status_code == 403
    # A change never uses a cookie without the header (a form or a script on another site).
    r = await client.post("/api/v1/me", headers={**jar, "Origin": OURS})
    assert r.status_code == 403 and r.json()["detail"] == "Not authenticated", r.text


async def test_a_change_needs_our_origin(client: AsyncClient) -> None:
    jar = {"Cookie": "bg_web_at=AT", "X-Session": "web"}
    no_origin = await client.post("/api/v1/me", headers=jar)
    assert no_origin.status_code == 403 and no_origin.json()["detail"]["code"] == "CSRF"
    evil = await client.post("/api/v1/me", headers={**jar, "Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.json()["detail"]["code"] == "CSRF"
    referer_only = await client.post("/api/v1/me", headers={**jar, "Referer": "https://evil.example/" + OURS})
    assert referer_only.status_code == 403
    assert (await client.post("/api/v1/me", headers={**jar, "Origin": OURS})).json() == {"token": "AT"}
    assert (await client.post("/api/v1/me", headers={**jar, "Referer": OURS + "/account"})).json() == {"token": "AT"}


async def test_the_apps_bearer_token_needs_no_origin(client: AsyncClient) -> None:
    r = await client.post("/api/v1/me", headers={"Authorization": "Bearer APP"})
    assert r.json() == {"token": "APP"}


async def test_an_expired_cookie_session_answers_401_so_the_page_refreshes(client: AsyncClient) -> None:
    r = await client.get("/api/v1/me", headers={"X-Session": "web"})
    assert r.status_code == 401, r.text


async def test_signing_out_clears_the_cookies(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/logout", headers={"Cookie": "bg_web_at=AT", "X-Session": "web", "Origin": OURS})
    assert r.status_code == 200
    cookies = set_cookies(r)
    assert cookies["bg_web_at"].startswith("bg_web_at=;") and "Max-Age=0" in cookies["bg_web_at"]
    assert cookies["bg_web_rt"].startswith("bg_web_rt=;") and "Max-Age=0" in cookies["bg_web_rt"]
