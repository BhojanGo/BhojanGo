"""Rotate QA logins' passwords (R13), printing no secret: sign in with the current password (and the
admin's authenticator), change it through POST /api/v1/me/password, write the new one only into
the logins file (mask.set_password), then sign in with it to prove it works.

    python tools/secrets/rotate_password.py --api https://<core-api> <email> [<email> ...]

Prints "rotated, file updated" once all succeed. On any failure it stops; if the file write fails
after the API changed the password, it changes it back. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mask  # noqa: E402
from totp_signin import finish  # noqa: E402


def _post(base: str, path: str, body: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(f"{base}/api/v1{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "bhojango-rotate",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:  # the API's message, masked (it never echoes a password, but be sure)
        raise RuntimeError(f"{path}: HTTP {e.code} {mask.mask(e.read().decode(errors='replace')[:200])}") from None


def sign_in(base: str, email: str, password: str, key: str | None) -> str:
    body = _post(base, "/auth/login", {"email": email, "password": password})
    return finish(lambda path, data: _post(base, path, data), email, body, {email: key} if key else None)["access_token"]


def rotate(base: str, email: str) -> None:
    old, key = mask.login(email)
    token = sign_in(base, email, old, key)
    new = secrets.token_urlsafe(18)  # 24 characters, ~144 bits
    _post(base, "/me/password", {"current_password": old, "new_password": new}, token)
    try:
        mask.set_password(email, new)
    except Exception:
        _post(base, "/me/password", {"current_password": new, "new_password": old}, sign_in(base, email, new, key))
        raise
    sign_in(base, email, new, key)  # the new password works


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("emails", nargs="+")
    a = ap.parse_args()
    for i, email in enumerate(a.emails, 1):
        try:
            rotate(a.api.rstrip("/"), email)
        except Exception as e:  # noqa: BLE001
            print(f"login {i} of {len(a.emails)} not rotated: {mask.mask(str(e))}", file=sys.stderr)
            return 1
    print("rotated, file updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
