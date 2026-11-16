"""Admin two-step sign-in for test tools (Round 8, D5). Stdlib only.

Admins answer /auth/login with ``mfa_required`` and an ``mfa_token``; the tool
then sends a 6-digit code from the admin's authenticator key to /auth/mfa/verify.
Keys: the logins file's fifth column on hosted QA (tools/seed SEED_PASSWORDS=random),
else the seed's fixed non-production key (tools/seed/data.py SEED_TOTP_SECRET).

A code is never accepted twice, so this remembers the last 30-second step used
per email and takes the next one (waiting for the clock if three were used).

    from totp_signin import keys_from_logins, next_code
"""
import base64
import hashlib
import hmac
import struct
import time

SEED_TOTP_SECRET = "BHOJANGOSEEDADMINTOTPKEY234567AB"  # gitleaks:allow (non-production seed key)
_last: dict[str, int] = {}


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    return str((struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000).zfill(6)


def next_code(email: str, secret: str | None = None) -> str:
    secret = secret or SEED_TOTP_SECRET
    while True:
        now = int(time.time() // 30)
        step = max(now - 1, _last.get(email, -1) + 1)
        if step <= now + 1:
            _last[email] = step
            return code_at(secret, step)
        time.sleep(1)


def logins(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f]


def passwords_from_logins(path: str) -> dict[str, str]:
    return {r[2]: r[3] for r in logins(path) if len(r) >= 4 and "@" in r[2]}


def keys_from_logins(path: str) -> dict[str, str]:
    """Admins' authenticator keys (fifth column) by email."""
    return {r[2]: r[4] for r in logins(path) if len(r) >= 5 and "@" in r[2] and r[4]}


def finish(post, email: str, body: dict, keys: dict[str, str] | None = None) -> dict:  # type: ignore[no-untyped-def]
    """Turn a sign-in answer into tokens. ``post(path, json) -> dict`` calls the API
    (path under /api/v1). An admin's answer asks for the second step: send a code."""
    if not body.get("mfa_required"):
        return body
    if body.get("enrolment_required"):
        raise RuntimeError(f"{email} has no authenticator yet: sign in once in the admin console to set it up")
    return post("/auth/mfa/verify", {"mfa_token": body["mfa_token"], "code": next_code(email, (keys or {}).get(email))})


def admin_console_second_step(page, email: str, keys: dict[str, str] | None = None) -> None:  # type: ignore[no-untyped-def]
    """Playwright: after "Sign in" on the admin console's /login, type the authenticator code."""
    box = page.get_by_label("6-digit code")
    box.wait_for(timeout=20000)
    box.fill(next_code(email, (keys or {}).get(email)))
    page.get_by_role("button", name="Continue").click()
