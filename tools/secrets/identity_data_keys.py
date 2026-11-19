"""Make IDENTITY_DATA_KEYS for one environment, once (R19). Stdlib only, no network.

    python tools/secrets/identity_data_keys.py

core_api encrypts admins' two-step (authenticator) secrets with these Fernet keys
(backend/core_api/modules/identity/service/totp.py) and refuses to start in production without
them. The value is a JSON list: the first key encrypts, every key decrypts.

The value goes to standard output only, as one line; the warning goes to standard error. Paste
it straight into Railway as a SEALED variable on core-api (production) and close the terminal.
Never save it in a file, the repo, a chat or a ticket: anyone with it can read every admin's
authenticator secret from a database copy. Writing standard output into a file is refused.

Rotating: run it again and set IDENTITY_DATA_KEYS to the new key FIRST and the old one after it,
e.g. ["<new>", "<old>"], so secrets made with the old key still decrypt. Needs the old value,
which a sealed variable won't show: so rotate only with the old value at hand, or re-enrol admins.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import stat
import sys

WARNING = """\
IDENTITY_DATA_KEYS (above): a secret for core-api in ONE environment.
- Paste it now into Railway as a SEALED variable (core-api, production), then clear this terminal.
- Never save it: not in a file, the repo, a chat or a ticket. Make a new one per environment.
- Lose it and admins must enrol their authenticator again; leak it and rotate it."""


def new_key() -> str:
    """A Fernet key: 32 random bytes, URL-safe base64 (what cryptography's Fernet.generate_key makes)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def value(n: int = 1) -> str:
    return json.dumps([new_key() for _ in range(n)])


def stdout_is_a_file() -> bool:
    try:
        return stat.S_ISREG(os.fstat(sys.stdout.fileno()).st_mode)
    except (OSError, ValueError, AttributeError):
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.parse_args(argv)
    if stdout_is_a_file():
        print("Refused: standard output is a file. The key must not be saved; run it in a terminal.", file=sys.stderr)
        return 2
    print(value())
    print(WARNING, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
