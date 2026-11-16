"""Test helper: sign in like a client does, including an admin's second step.

Unit tests (here) and integration tests (core_api/integration) use it. An admin
without an authenticator is enrolled on the way (the emailed code is the fixed
123456 for @example.com outside production); seeded admins use the seed's
non-production authenticator key (tools/seed/data.py SEED_TOTP_SECRET).

A code is never accepted twice (RFC 6238 5.2), so the helper remembers the last
step it used per email and takes the next one; at most three sign-ins of one
admin fit in 30 seconds before it waits for the clock.
"""
import asyncio

from httpx import AsyncClient

from core_api.modules.identity.service import totp

# The seed's authenticator key for its admin accounts outside production (local and CI).
# Keep in step with tools/seed/data.py SEED_TOTP_SECRET.
SEED_TOTP_SECRET = "BHOJANGOSEEDADMINTOTPKEY234567AB"
FIXED_EMAIL_CODE = "123456"

secrets_by_email: dict[str, str] = {}
_last_step: dict[str, int] = {}


async def next_code(email: str, secret: str) -> str:
    while True:
        now = totp.current_step()
        step = max(now - totp.DRIFT_STEPS, _last_step.get(email, -1) + 1)
        if step <= now + totp.DRIFT_STEPS:
            _last_step[email] = step
            return totp.code_at(secret, step)
        await asyncio.sleep(1)


async def finish(client: AsyncClient, email: str, body: dict, *, secret: str | None = None) -> dict:
    """Turn a sign-in answer into tokens: passes an admin's second step if asked for."""
    if not body.get("mfa_required"):
        return body
    token = body["mfa_token"]
    if body["enrolment_required"]:
        r = await client.post("/api/v1/auth/mfa/enrol/start", json={"mfa_token": token, "email_code": FIXED_EMAIL_CODE})
        assert r.status_code == 200, r.text
        key = r.json()["secret"]
        secrets_by_email[email] = key
        step = totp.current_step()
        _last_step[email] = step
        r = await client.post("/api/v1/auth/mfa/enrol/confirm", json={"mfa_token": token, "code": totp.code_at(key, step)})
    else:
        key = secret or secrets_by_email.get(email) or SEED_TOTP_SECRET
        r = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": token, "code": await next_code(email, key)})
    assert r.status_code == 200, r.text
    return r.json()


async def login_response(client: AsyncClient, email: str, password: str):  # type: ignore[no-untyped-def]
    """POST /auth/login and, for an admin, the second step: the final response."""
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if r.status_code != 200 or not r.json().get("mfa_required"):
        return r
    body = await finish(client, email, r.json())
    import httpx

    return httpx.Response(200, json=body)


async def password_sign_in(client: AsyncClient, email: str, password: str) -> dict:
    r = await login_response(client, email, password)
    assert r.status_code == 200, r.text
    return r.json()


async def email_sign_up(client: AsyncClient, email: str, password: str = "Long-enough-pass1", *, country: str = "US",
                        full_name: str = "Test User") -> dict:
    """A new account through /auth/email/sign-up + the emailed code (fixed for @example.com)."""
    r = await client.post("/api/v1/auth/email/sign-up", json={
        "email": email, "password": password, "country": country, "full_name": full_name})
    assert r.status_code == 202, r.text
    r = await client.post("/api/v1/auth/email/verify", json={"email": email, "code": FIXED_EMAIL_CODE})
    assert r.status_code == 200, r.text
    return r.json()
