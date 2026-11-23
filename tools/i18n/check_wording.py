"""Fail if text a person reads calls a delivery partner a "rider", names a "Partner app",
or writes the brand other than "BhojanGo" (the wordmark: "bhojango", "Bhojango", "Bhojan Go").

    python tools/i18n/check_wording.py          (make ci-i18n)
    python tools/i18n/check_wording_test.py     (its unit tests, also in make ci-i18n)

The words (docs: Round 8 wording contract): delivery people are "delivery partners"
(in every language: डिलीवरी पार्टनर, డెలివరీ పార్ట్‌నర్, repartidor ...), restaurants are
"restaurant partners" (R30; never "kitchen": tools/i18n/wording_scan.py), and the apps are BhojanGo,
BhojanGo Restaurant and BhojanGo Delivery.
Code names stay: identifiers, routes, i18n keys, DB columns, comments and tests may
say "rider".

What is checked:
  packages/i18n/messages/*.json        every message VALUE ({placeholders} removed)
  backend/shared/texts.py, worker      every text in entries() (push, SMS, email, chat)
    messages.py
  apps/*/app.json, app.config.js       the app names and permission sentences
  .tsx/.ts/.jsx/.js under the apps and  JSX text, and string literals that read as
    packages/mobile-core, packages/ui  words (they have a space, or start with a
                                       capital): labels, aria-label, title, alt ...
A string that is a single lowercase word ("rider", "rider-docs", "/riders/me",
"riders.edit") is a code name and is allowed.

Stdlib only (the Repo checks job has Python and nothing else).
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]

# "rider", "riders", "rider's", "riders'" as a word, not part of an identifier or a path
# ("rider.id", "rider_id", "riderId", "/riders/me", "bhojango-rider").
EN_WORD = re.compile(r"(?<![\w./\-])riders?(?:'s|')?(?![\w\-/]|\.\w|\(|\?\.)", re.IGNORECASE)
# The same word written in the other scripts, as a stem: it takes suffixes there
# (रायडरला, రైడర్‌కు, ரைடருக்கு, ರೈಡರನ್ನು, রাইডারের), some of which replace the final virama.
SCRIPT_WORDS = ("राइडर", "रायडर", "రైడర", "ரைடர", "ರೈಡರ", "রাইডার")
# The old app names.
APP_NAMES = re.compile(r"\b(?:partner|rider)\s+app\b|BhojanGo\s+(?:Partner|Rider)\b", re.IGNORECASE)

# The wordmark (R12): the brand is written "BhojanGo" (capital B and G) wherever a person reads it,
# in every app, the admin and email. Code names stay ("bhojango-rider", "@bhojango/ui",
# "bill.bhojango", "support@bhojango.com", issuer "bhojango" in a test).
WORDMARK = re.compile(r"(?<![\w./@\-:])bhojan[ \-]?go(?![\w./@\-:_])", re.IGNORECASE)

PLACEHOLDER = re.compile(r"\{[^{}]*\}")  # {rider} in a message, ${x} in a template literal


def problem(text: str) -> str | None:
    """Why ``text`` (words a person reads) breaks the wording rule, or None."""
    t = PLACEHOLDER.sub(" ", text)
    t = PLACEHOLDER.sub(" ", t)  # nested ICU: {n, plural, one {..} other {..}}
    for m in WORDMARK.finditer(t):
        if m.group(0) != "BhojanGo" and t.strip() != "BHOJANGO":  # "BHOJANGO" alone: the bill's payee code
            return f'writes the brand "{m.group(0)}": write "BhojanGo"'
    m = APP_NAMES.search(t)
    if m:
        return f'names an old app ("{m.group(0)}"): say BhojanGo Restaurant / BhojanGo Delivery'
    m = EN_WORD.search(t)
    if m:
        return f'says "{m.group(0)}": say "delivery partner"'
    for w in SCRIPT_WORDS:
        if w in t:
            return f'says "{w}": say "delivery partner" in the language (packages/i18n/REVIEW.md)'
    return None


# ── i18n messages ─────────────────────────────────────────────────────────────

def flat(o: object, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat(v, f"{prefix}{k}."))
    elif isinstance(o, str):
        out[prefix[:-1]] = o
    return out


def check_messages(messages_dir: Path) -> list[str]:
    found = []
    for f in sorted(messages_dir.glob("*.json")):
        for key, value in flat(json.loads(f.read_text(encoding="utf-8"))).items():
            why = problem(value)
            if why:
                found.append(f"packages/i18n/messages/{f.name}: {key} {why}")
    return found


# ── backend texts ─────────────────────────────────────────────────────────────

def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def backend_catalogues() -> dict[str, dict[str, dict[str, str]]]:
    sys.path.insert(0, str(ROOT / "backend"))
    texts = _load(ROOT / "backend" / "shared" / "texts.py", "shared.texts")
    sys.modules["shared.texts"] = texts
    messages = _load(ROOT / "backend" / "worker" / "app" / "services" / "messages.py", "worker_messages")
    return {"backend/shared/texts.py": texts.entries(), "backend/worker/app/services/messages.py": messages.entries()}


def check_catalogues(cats: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    found = []
    for source, entries in cats.items():
        for name, texts in entries.items():
            for lang, value in texts.items():
                why = problem(value) if isinstance(value, str) else None
                if why:
                    found.append(f"{source}: {name} [{lang}] {why}")
    return found


# ── app manifests ─────────────────────────────────────────────────────────────

def strings_in(o: object) -> list[str]:
    if isinstance(o, str):
        return [o]
    if isinstance(o, dict):
        return [s for v in o.values() for s in strings_in(v)]
    if isinstance(o, list):
        return [s for v in o for s in strings_in(v)]
    return []


def check_manifest(path: Path, rel: str) -> list[str]:
    found = []
    for s in strings_in(json.loads(path.read_text(encoding="utf-8"))):
        why = problem(s) if (" " in s or s[:1].isupper()) else None
        if why:
            found.append(f"{rel}: {s!r} {why}")
    return found


# ── source code: JSX text and string literals ────────────────────────────────

SOURCE_DIRS = ("apps/web/src", "apps/admin/src", "apps/customer", "apps/partner", "apps/rider",
               "packages/mobile-core/src", "packages/ui/src", "packages/ui")
SOURCE_EXT = {".tsx", ".ts", ".jsx", ".js", ".mjs"}
SKIP_PARTS = {"node_modules", ".next", ".expo", "dist", "build", ".maestro", "__tests__", "e2e", "android", "ios",
              "coverage", ".turbo", "test", "tests"}
SKIP_NAME = re.compile(r"\.(test|spec)\.|\.d\.ts$|^(next-env|metro\.config|babel\.config|eslint\.config|jest\.config"
                       r"|tailwind\.config|postcss\.config|vitest\.config)\.")
ENTITY = re.compile(r"&(?:apos|rsquo|#39|#x27);")


def lex(src: str) -> tuple[list[tuple[int, str]], str]:
    """(string literals as (line, text), the code with comments removed and strings blanked).

    Quotes end at a newline, so an apostrophe in JSX text ("Don't") swallows at most
    the rest of its line, which is then checked as a string (it is words anyway)."""
    out: list[str] = []
    strings: list[tuple[int, str]] = []
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "/" and src.startswith("//", i) and (i == 0 or src[i - 1] != ":"):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            out.append("\n" * src.count("\n", i, j))
            i = j
            continue
        if c in "\"'`":
            j, start = i + 1, line
            buf = []
            while j < n and src[j] != c:
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if src[j] == "\n":
                    if c != "`":
                        break
                    line += 1
                buf.append(src[j])
                j += 1
            strings.append((start, "".join(buf)))
            out.append('""' + "\n" * "".join(buf).count("\n"))
            i = j + 1 if j < n and src[j] == c else j
            continue
        if c == "\n":
            line += 1
        out.append(c)
        i += 1
    return strings, "".join(out)


# Text between tags or {expressions}: <p>Ask {name} the rider</p> gives "Ask " and " the rider".
JSX_TEXT = re.compile(r"[>}]([^<>{}]+)[<{]")
# A stretch of code between a > or } and a < or {, not text: it has operators, a blanked
# string ("" from t("key")), a declaration, a type (x: string), or the word as a key,
# an optional field or a condition (rider: / rider?: / rider ? a : b).
CODE_HINT = re.compile(r'=|&&|\|\||""|\b(?:return|const|let|export|function|import)\b'
                       r'|\??:\s*(?:string|number|boolean|null|undefined)\b|\briders?\s*\??\s*:|\briders?\s*\?\s')


def check_source(src: str, rel: str) -> list[str]:
    found = []
    strings, code = lex(src)
    for line, s in strings:
        if " " in s.strip() or s[:1].isupper() or "\n" in s:
            why = problem(ENTITY.sub("'", s))
            if why:
                found.append(f"{rel}:{line}: {s.strip()[:80]!r} {why}")
    for m in JSX_TEXT.finditer(code):
        text = ENTITY.sub("'", m.group(1))
        if not text.strip() or CODE_HINT.search(re.sub(r"&\w+;|&#\w+;", "", text)):
            continue
        why = problem(text)
        if why:
            line = code.count("\n", 0, m.start(1)) + 1
            found.append(f"{rel}:{line}: {' '.join(text.split())[:80]!r} {why}")
    return found


def source_files(root: Path) -> list[Path]:
    seen: set[Path] = set()
    for d in SOURCE_DIRS:
        base = root / d
        if not base.exists():
            continue
        # os.walk, pruned: never descends into node_modules (deep paths break on Windows)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [n for n in dirnames if n not in SKIP_PARTS]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix not in SOURCE_EXT or p in seen or SKIP_NAME.search(name):
                    continue
                if SKIP_PARTS.intersection(p.relative_to(root).parts):
                    continue
                seen.add(p)
    return sorted(seen)


# Markup a person reads that lives in backend code (the email layout's header row).
MARKUP_FILES = ("backend/worker/app/services/messages.py", "backend/shared/texts.py")
TAG_TEXT = re.compile(r">([^<>{}]+)<")


def check_markup(root: Path = ROOT) -> list[str]:
    found = []
    for rel in MARKUP_FILES:
        p = root / rel
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        for m in TAG_TEXT.finditer(src):
            text = m.group(1)
            if not WORDMARK.search(text):
                continue
            why = problem(text)
            if why:
                found.append(f"{rel}:{src.count(chr(10), 0, m.start(1)) + 1}: {text.strip()[:80]!r} {why}")
    return found


def check_repo(root: Path = ROOT) -> list[str]:
    found = check_messages(root / "packages" / "i18n" / "messages")
    found += check_catalogues(backend_catalogues())
    found += check_markup(root)
    for app in ("customer", "partner", "rider"):
        manifest = root / "apps" / app / "app.json"
        if manifest.exists():
            found += check_manifest(manifest, f"apps/{app}/app.json")
    for p in source_files(root):
        found += check_source(p.read_text(encoding="utf-8", errors="replace"), p.relative_to(root).as_posix())
    return found


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    found = check_repo()
    for f in found:
        print(f, file=sys.stderr)
    if found:
        print(f"\n{len(found)} text(s) say rider, an old app name or a wrong wordmark. People read "
              "\"delivery partner\", BhojanGo Restaurant / BhojanGo Delivery, and \"BhojanGo\".", file=sys.stderr)
        return 1
    print("wording ok: no user-facing 'rider', old app name or lowercase wordmark in messages, backend texts, app names or app code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
