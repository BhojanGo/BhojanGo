"""Where the secrets files live (R25): the one place this is decided. Stdlib only.

Default: the "Products" folder in the DeepTrics LLC OneDrive, under the user's home folder (outside
the repo). Override with the environment variable BHOJANGO_SECRETS_DIR (tests, another machine).
"""
from __future__ import annotations

import os
from pathlib import Path

ENV = "BHOJANGO_SECRETS_DIR"
DEFAULT_DIR = Path.home() / "OneDrive - DeepTrics LLC" / "Products"
FILE_NAMES = ("BhojanGo_QA_Logins.txt", "BhojanGo_Railway_Tokens.txt", "BhojanGo_Stripe_Keys.txt")


def secrets_dir() -> Path:
    """BHOJANGO_SECRETS_DIR if set, else the default."""
    value = os.environ.get(ENV, "").strip()
    return Path(value) if value else DEFAULT_DIR


def missing_files(directory: Path | None = None) -> list[Path]:
    """The secrets files that aren't there (empty: all found)."""
    d = directory or secrets_dir()
    return [d / name for name in FILE_NAMES if not (d / name).is_file()]
