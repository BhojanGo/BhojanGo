"""Never print a secret (R13). Masks every password, authenticator key, token and API key we hold
in any text, and reads or changes logins without showing them.

Where secrets live (a folder outside the repo: BHOJANGO_SECRETS_DIR, else E2E_LOGINS_FILE's folder):
  BhojanGo_QA_Logins.txt       the QA logins (tab-separated: ... email, password[, authenticator key])
  BhojanGo_Railway_Tokens.txt  Railway tokens ("Name: value")
  BhojanGo_Stripe_Keys.txt     Stripe test keys ("name: value")
plus the values of environment variables named like *TOKEN*, *SECRET*, *PASSWORD*, *_KEY.

    <cmd> 2>&1 | python tools/secrets/mask.py          mask a command's output
    python tools/secrets/mask.py run -- <cmd> [args]   run a command, its output masked, its exit code kept
    python tools/secrets/mask.py files <dir> [...]     mask files in place (logs); prints counts only

In Python: ``from mask import mask, login, set_password`` (tools/secrets on sys.path).
Stdlib only. Prints no secret, ever: a value it knows becomes <redacted>, and so does anything
shaped like a Stripe key, a bearer token or a JWT.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

DIR = Path(os.environ.get("BHOJANGO_SECRETS_DIR")
           or (str(Path(os.environ["E2E_LOGINS_FILE"]).parent) if os.environ.get("E2E_LOGINS_FILE") else "")
           or Path.home() / "bhojango-secrets")  # a folder outside the repo; never commit its path
LOGINS = DIR / "BhojanGo_QA_Logins.txt"
FILES = (LOGINS, DIR / "BhojanGo_Railway_Tokens.txt", DIR / "BhojanGo_Stripe_Keys.txt")
FILE_NAMES = tuple(p.name for p in FILES)
MASK = "<redacted>"
SHAPES = re.compile(
    r"\b(?:sk|rk|pk)_(?:test|live)_[A-Za-z0-9]{8,}"  # Stripe API keys
    r"|\bwhsec_[A-Za-z0-9]{8,}"                       # Stripe webhook secrets
    r"|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"  # JWTs
    r"|(?<=Bearer )[A-Za-z0-9._~+/=-]{12,}"            # bearer tokens
)
ENV_NAME = re.compile(r"TOKEN|SECRET|PASSWORD|_KEY$|^KEY$", re.I)


def _rows() -> list[list[str]]:
    try:
        return [line.rstrip("\n").split("\t") for line in LOGINS.read_text(encoding="utf-8").splitlines()]
    except OSError:
        return []


def secret_values() -> list[str]:
    """Every secret string we know, longest first (so a value inside another is masked whole)."""
    found: set[str] = set()
    for row in _rows():
        for i, col in enumerate(row):
            if "@" in col and "." in col:  # an email: the next columns are its password and key
                found.update(c.strip() for c in row[i + 1:i + 3] if len(c.strip()) >= 8)
    for f in FILES[1:]:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                value = re.split(r"[:=]", line, maxsplit=1)[-1].strip()
                if len(value) >= 8 and " " not in value:
                    found.add(value)
        except OSError:
            pass
    found.update(v for k, v in os.environ.items() if ENV_NAME.search(k) and len(v) >= 8)
    return sorted(found, key=len, reverse=True)


def mask(text: str, values: list[str] | None = None) -> str:
    for v in values if values is not None else secret_values():
        text = text.replace(v, MASK)
    return SHAPES.sub(MASK, text)


def login(email: str) -> tuple[str, str | None]:
    """(password, authenticator key or None) for a QA login. Never print what this returns."""
    for row in _rows():
        if email in row:
            i = row.index(email)
            key = row[i + 2].strip() if len(row) > i + 2 and row[i + 2].strip() else None
            return row[i + 1].strip(), key
    raise KeyError(f"no QA login for {email}")


def set_password(email: str, new: str) -> None:
    """Write a QA login's new password into the logins file (the only place it is kept)."""
    lines = LOGINS.read_text(encoding="utf-8").splitlines(keepends=True)
    for n, line in enumerate(lines):
        cols = line.rstrip("\n").split("\t")
        if email in cols:
            cols[cols.index(email) + 1] = new
            lines[n] = "\t".join(cols) + ("\n" if line.endswith("\n") else "")
            tmp = LOGINS.with_suffix(".tmp")
            tmp.write_text("".join(lines), encoding="utf-8")
            os.replace(tmp, LOGINS)
            return
    raise KeyError(f"no QA login for {email}")


def _files(dirs: list[str]) -> None:
    values, changed, scanned = secret_values(), 0, 0
    for d in dirs:
        for root, _, names in os.walk(d):
            for name in names:
                path = os.path.join(root, name)
                if name.endswith((".png", ".jpg", ".mp4", ".webp")) or os.path.getsize(path) > 50_000_000:
                    continue
                scanned += 1
                try:
                    text = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
                except OSError:
                    continue
                new = mask(text, values)
                if new != text:
                    Path(path).write_text(new, encoding="utf-8", errors="surrogateescape")
                    changed += 1
    print(f"masked secrets in {changed} of {scanned} files")


def main(argv: list[str]) -> int:
    if argv[:1] == ["files"]:
        _files(argv[1:])
        return 0
    values = secret_values()
    if argv[:1] == ["run"]:
        cmd = argv[2:] if argv[1:2] == ["--"] else argv[1:]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        assert p.stdout
        for line in p.stdout:
            sys.stdout.write(mask(line, values))
            sys.stdout.flush()
        return p.wait()
    for line in sys.stdin:
        sys.stdout.write(mask(line, values))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
