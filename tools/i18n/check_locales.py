"""Fail if a user-facing text lacks a language that a live country lists in Markets.

    python tools/i18n/check_locales.py              (make ci-i18n)
    python tools/i18n/check_locales.py --self-test  (proves it fails on a missing key)

The countries come from the seed (tools/seed/data.py COUNTRIES): every country
whose status is live or beta, and each of its Markets locales mapped to its
language (hi-IN → hi, es-US → es). For each of those languages:

  packages/i18n/messages/<lang>.json   every English key (website, apps), non-empty
  backend/worker/app/services/messages.py   push/SMS/email messages, "Arriving
                                       around", item counts, the email footer
                                       (entries())
  backend/shared/texts.py              quick messages (chat), names, the sign-in
                                       code SMS, the welcome email (entries())

Backend texts must also keep English's {placeholders}, and the backend's
language_for must map the locale to its own language (not fall back to English).
English is the source; other languages are machine translations listed in
packages/i18n/REVIEW.md until a native reviewer signs them off.

Stdlib only (the Repo checks job has Python and nothing else).
"""
import argparse
import importlib.util
import json
import shutil
import string
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
MESSAGES = ROOT / "packages" / "i18n" / "messages"
OPEN = {"live", "beta"}


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def backend() -> tuple[ModuleType, ModuleType]:
    """shared/texts.py and the worker's messages.py (which imports shared.texts)."""
    sys.path.insert(0, str(ROOT / "backend"))
    texts = load(ROOT / "backend" / "shared" / "texts.py", "shared.texts")
    sys.modules["shared.texts"] = texts
    messages = load(ROOT / "backend" / "worker" / "app" / "services" / "messages.py", "worker_messages")
    return texts, messages


def live_countries() -> list[dict]:
    seed = load(ROOT / "tools" / "seed" / "data.py", "seed_data")
    return [c for c in seed.COUNTRIES if c.get("status") in OPEN]  # NZ (tools/web/third_city.py) is a test fixture


def required(countries: list[dict]) -> dict[str, list[str]]:
    """language → the "XX:locale" entries that need it (live and beta countries only)."""
    need: dict[str, list[str]] = {}
    for c in countries:
        if c.get("status") not in OPEN:
            continue
        for loc in c.get("locales") or []:
            need.setdefault(loc.replace("_", "-").split("-")[0].lower(), []).append(f"{c['code']}:{loc}")
    return need


def flat(o: dict, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in o.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def fields(text: str) -> list[str]:
    return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f)


def check(countries: list[dict], messages_dir: Path, catalogues: dict[str, dict[str, dict[str, str]]],
          language_for=None) -> list[str]:  # type: ignore[no-untyped-def]
    """Every problem, as a line. Empty when every live country's languages are complete."""
    problems: list[str] = []
    need = required(countries)
    en = flat(json.loads((messages_dir / "en.json").read_text(encoding="utf-8")))
    for lang, who in sorted(need.items()):
        if lang == "en":
            continue
        where = ", ".join(who)
        file = messages_dir / f"{lang}.json"
        if not file.exists():
            problems.append(f"messages/{lang}.json: missing ({where} is listed by a live country)")
            continue
        msgs = flat(json.loads(file.read_text(encoding="utf-8")))
        for key in en:
            v = msgs.get(key)
            if not isinstance(v, str) or not v.strip():
                problems.append(f"messages/{lang}.json: {key} is {'empty' if key in msgs else 'missing'} (needed by {where})")
        if language_for is not None and language_for(lang) != lang:
            problems.append(f"backend language_for({lang!r}) falls back to English (needed by {where})")
    for source, entries in catalogues.items():
        for name, texts in entries.items():
            base = texts.get("en", "")
            if not base.strip():
                problems.append(f"{source}: {name} has no English")
                continue
            for lang, who in sorted(need.items()):
                v = texts.get(lang)
                if not isinstance(v, str) or not v.strip():
                    problems.append(f"{source}: {name} is {'empty' if lang in texts else 'missing'} in {lang} "
                                    f"(needed by {', '.join(who)})")
                elif fields(v) != fields(base):
                    problems.append(f"{source}: {name} [{lang}] has {{{','.join(fields(v))}}}, "
                                    f"English has {{{','.join(fields(base))}}}")
    return problems


def catalogues(texts: ModuleType, messages: ModuleType) -> dict[str, dict[str, dict[str, str]]]:
    return {"backend/worker/app/services/messages.py": messages.entries(), "backend/shared/texts.py": texts.entries()}


def self_test() -> int:
    """The check must fail on a missing JSON key, a missing backend language, a
    changed placeholder and a live locale nobody translated; and pass on the repo."""
    texts, messages = backend()
    cats = catalogues(texts, messages)
    countries = live_countries()
    assert countries, "no live countries in tools/seed/data.py"
    assert not check(countries, MESSAGES, cats, texts.language_for), "the repo itself should pass"
    lang = next(l for l in required(countries) if l != "en")

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for f in MESSAGES.glob("*.json"):
            shutil.copy(f, d / f.name)
        data = json.loads((d / f"{lang}.json").read_text(encoding="utf-8"))
        first = next(iter(data))
        removed = data.pop(first)
        key = first if isinstance(removed, str) else f"{first}.{next(iter(flat(removed)))}"
        (d / f"{lang}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        got = check(countries, d, {}, texts.language_for)
        assert any(f"messages/{lang}.json: {key} is missing" in p for p in got), got[:3]

    broken = {src: {n: dict(t) for n, t in e.items()} for src, e in cats.items()}
    src = "backend/worker/app/services/messages.py"
    del broken[src]["order_placed.body"][lang]
    broken[src]["arriving"] = {**broken[src]["arriving"], lang: "{when}"}
    got = check(countries, MESSAGES, broken, texts.language_for)
    assert any(f"order_placed.body is missing in {lang}" in p for p in got), got
    assert any(f"arriving [{lang}] has {{when}}" in p for p in got), got

    newcomer = [*countries, {"code": "ZZ", "status": "live", "locales": ["en-ZZ", "xx-ZZ"]}]
    got = check(newcomer, MESSAGES, cats, texts.language_for)
    assert any("xx.json: missing" in p for p in got), got
    assert any("missing in xx (needed by ZZ:xx-ZZ)" in p for p in got), got
    # A draft country's languages are not required yet.
    assert not check([*countries, {"code": "ZZ", "status": "draft", "locales": ["xx-ZZ"]}], MESSAGES, cats)
    print("check_locales self-test ok: fails on a missing key, language, placeholder and locale")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    if ap.parse_args().self_test:
        return self_test()
    texts, messages = backend()
    countries = live_countries()
    problems = check(countries, MESSAGES, catalogues(texts, messages), texts.language_for)
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} missing translation(s). Add them (machine translations are fine: list them in "
              "packages/i18n/REVIEW.md).", file=sys.stderr)
        return 1
    langs = sorted(required(countries))
    n = sum(len(e) for e in catalogues(texts, messages).values())
    print(f"locales ok: {', '.join(c['code'] for c in countries)} need {', '.join(langs)}; "
          f"every app/web key and {n} backend texts present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
