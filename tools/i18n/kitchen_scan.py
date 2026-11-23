"""R30: no customer- or restaurant-facing "kitchen". Lists every user-visible string that still says kitchen:

  * locale values (packages/i18n/messages/*.json), in every language: "kitchen" and each language's own word
  * string literals and JSX text in the apps and shared packages (tests, stories and code identifiers aside:
    a string with no space that looks like a key, path, test id or route is code, not copy)
  * user-facing backend strings (string constants in core_api, docstrings aside) and the seeded help / legal text

    python tools/i18n/kitchen_scan.py            # prints each hit; exit 1 if any
    python tools/i18n/kitchen_scan.py --summary  # counts only

Code identifiers (KitchenCard, kitchen_join, /kitchens/join, "kitchen" as an API field...) stay: they are not copy.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# "kitchen" in each locale's own words (the brief: every language file)
NATIVE = {
    "en": [r"kitchen"],
    "es": [r"kitchen", r"\bcocinas?\b"],
    "hi": [r"kitchen", "रसोई", "किचन"],
    "bn": [r"kitchen", "রান্নাঘর", "কিচেন"],
    "mr": [r"kitchen", "स्वयंपाकघर", "किचन"],
    "ta": [r"kitchen", "சமையலறை", "கிச்சன்"],
    "te": [r"kitchen", "వంటగది", "వంటశాల", "కిచెన్"],
    "kn": [r"kitchen", "ಅಡುಗೆಮನೆ", "ಕಿಚನ್"],
}
WORD = re.compile(r"kitchen", re.I)
SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".expo", "test", "tests", "__tests__", ".maestro", "e2e", "android", "ios"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx"}
STRING = re.compile(r"""(?P<q>["'`])(?P<s>(?:\\.|(?!(?P=q)).)*?)(?P=q)""", re.S)
JSX_TEXT = re.compile(r">([^<>{}]*kitchen[^<>{}]*)<", re.I)  # also across lines (text on its own line)
# JSX-text candidates that are really TypeScript between a ">" and a "<" (generics, comparisons, comments)
CODEISH = re.compile(r"\bif \(|: Record|; //|=>|&&|\|\||\bconst\b|\breturn\b|: [A-Z]\w*<|\w\(|\)\s*[;{]|^\s*//|\*/|/\*")
# A restaurant's own trading name (demo seed data) is the business's name, not BhojanGo's wording: allowed.
NAMES = re.compile(r"\b(Spice Route|Basque Corner|Kesar) Kitchen\b")
ICU = re.compile(r"\{[^{}]*\}")  # a message's {placeholder}: a variable name, not copy
PLACE = re.compile(r"\$\{[^{}]*\}")  # a template literal's ${...}: code


def flat(d: dict, p: str = ""):  # type: ignore[no-untyped-def]
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flat(v, p + k + ".")
        else:
            yield p + k, v


PROSE = re.compile(r"(?<![#/.\w-])kitchens?(?![\w-]|\.\w)", re.I)  # the word in prose, not kitchen_id / #kitchens / kitchen.name


def is_code(s: str) -> bool:
    """A key, identifier, path, route, test id, import or CSS: not something a person reads."""
    t = NAMES.sub("", s).strip()
    if not t or " " not in t:
        return True
    return bool(re.fullmatch(r"[\w./:@#?=&${}\-\[\]()*,]+", t))


def locale_hits() -> list[str]:
    out = []
    for f in sorted((ROOT / "packages/i18n/messages").glob("*.json")):
        pats = [re.compile(p, re.I) for p in NATIVE.get(f.stem, ["kitchen"])]
        for k, v in flat(json.loads(f.read_text(encoding="utf-8"))):
            if isinstance(v, str) and any(p.search(ICU.sub("", v)) for p in pats):
                out.append(f"{f.relative_to(ROOT)}: {k} = {v[:120]!r}")
    return out


def code_hits() -> list[str]:
    out = []
    for base in ("apps", "packages"):
        for f in (ROOT / base).rglob("*"):
            if f.suffix not in CODE_EXT or any(part in SKIP_DIRS for part in f.parts) or ".test." in f.name:
                continue
            if "i18n" in f.parts and f.name in ("all-messages.js", "all-messages.d.ts"):
                continue  # generated from the locale files, checked above
            text = f.read_text(encoding="utf-8", errors="ignore")
            if not WORD.search(text):
                continue
            if f.suffix in (".tsx", ".jsx"):
                for m in JSX_TEXT.finditer(text):
                    body = m.group(1)
                    if PROSE.search(NAMES.sub("", body)) and not CODEISH.search(body):
                        n = text.count(chr(10), 0, m.start(1) + len(body) - len(body.lstrip())) + 1
                        out.append(f"{f.relative_to(ROOT)}:{n}: {' '.join(body.split())[:120]!r}")
            for n, line in enumerate(text.splitlines(), 1):
                if not WORD.search(line) or line.lstrip().startswith(("//", "*", "/*", "import ")):
                    continue
                for m in STRING.finditer(line):
                    s = m.group("s")
                    if WORD.search(s) and not is_code(PLACE.sub("", s)) and not s.lstrip().startswith(("//", "/*"))                             and "=>" not in s and ": Record" not in s and WORD.search(PLACE.sub("", s)) and PROSE.search(s):
                        out.append(f"{f.relative_to(ROOT)}:{n}: {s[:120]!r}")

    return out


def config_hits() -> list[str]:
    """App names and permission prompts in apps/*/app.json (what the stores and the phone show)."""
    out = []
    for f in sorted((ROOT / "apps").glob("*/app.json")):
        def walk(v, path=""):  # type: ignore[no-untyped-def]
            if isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{path}.{k}")
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{path}[{i}]")
            elif isinstance(v, str) and " " in v and PROSE.search(v):
                out.append(f"{f.relative_to(ROOT)}: {path} = {v[:120]!r}")
        walk(json.loads(f.read_text(encoding="utf-8")))
    return out


def python_hits() -> list[str]:
    out = []
    native = [re.compile(w) for lang, ws in NATIVE.items() if lang not in ("en", "es") for w in ws[1:]]
    native.append(re.compile(r"\bcocinas?\b", re.I))
    files = [f for d in ("core_api", "shared", "realtime/app", "worker/app", "tools") for f in (ROOT / "backend" / d).rglob("*.py")]
    for f in files:
        if any(part in ("tests", "integration", "migrations") for part in f.parts) or f.name.endswith("_test.py"):
            continue
        text = f.read_text(encoding="utf-8")
        if not WORD.search(text) and not any(w.search(text) for w in native):
            continue
        tree = ast.parse(text)
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                v = ICU.sub("", NAMES.sub("", n.value))
                if (PROSE.search(v) or any(w.search(v) for w in native)) and not is_code(n.value):
                    out.append(f"{f.relative_to(ROOT)}:{n.lineno}: {n.value[:120]!r}")
    return out


def content_hits() -> list[str]:
    """Help articles and legal documents, in every language (links and slugs like /help/add-your-kitchen are code)."""
    out = []
    for base in ("tools/seed/help", "tools/seed/legal"):
        for f in sorted((ROOT / base).rglob("*.md")):
            lang = f.parent.name if base.endswith("help") else "en"
            native = [re.compile(w) for w in NATIVE.get(lang, [])[1:] if not w.startswith("\\b")]
            if lang == "es":
                native = [re.compile(r"\bcocinas?\b", re.I)]
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if line.startswith(("slug:", "related:", "id:")):
                    continue
                text = NAMES.sub("", re.sub(r"\]\([^)]*\)", "]", line))
                if PROSE.search(text) or any(w.search(text) for w in native):
                    out.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:120]!r}")
    return out


def self_test() -> int:
    """The matchers find copy and leave code alone (each case is a bug this scanner once had)."""
    prose = ["Search dishes and kitchens", "what the kitchen is paid.", "Kitchen's treat", "KITCHEN"]
    code = ["kitchen_id", "#kitchens", "/kitchens/join", "kitchen.name", "kitchenQ", "add-your-kitchen"]
    assert all(PROSE.search(t) for t in prose), prose
    assert not any(PROSE.search(t) for t in code), code
    jsx = ">\n        Test site: demo kitchens, no real orders or payments\n      <"  # JSX text on its own line
    assert [m.group(1) for m in JSX_TEXT.finditer(jsx) if not CODEISH.search(m.group(1))]
    for ts in (">, kitchens: Record<", "> 0; if (kitchen) return <", ">a; // the kitchen's x <"):  # TypeScript, not text
        assert CODEISH.search(JSX_TEXT.search(ts).group(1)), ts
    assert re.search(r"\bcocinas?\b", "Repartidor en camino a la cocina", re.I)
    assert ICU.sub("", "Order again from {kitchen}") == "Order again from "
    assert NAMES.sub("", "Spice Route Kitchen").strip() == "" and is_code("Spice Route Kitchen")
    print("kitchen_scan self-test ok")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    groups = {"locales": locale_hits(), "app and package strings": code_hits(), "app configs": config_hits(), "backend strings": python_hits(),
              "help and legal": content_hits()}
    total = sum(len(v) for v in groups.values())
    for name, hits in groups.items():
        print(f"{name}: {len(hits)}")
        if "--summary" not in sys.argv:
            for h in hits:
                print("  " + h)
    print(f"total: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
