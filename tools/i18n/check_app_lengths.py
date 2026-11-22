"""Fail if a translation is too wide for the place the Expo apps show it in one line (R27).

    python tools/i18n/check_app_lengths.py              (make ci-i18n)
    python tools/i18n/check_app_lengths.py --self-test  (proves it fails on a long label)

The website is rendered in every language at 360 and 1440 px in CI (tools/web/i18n_layout.py).
The three Expo apps can't be rendered screen by screen in CI without an emulator, so this
covers what can be checked from the catalog: every label the apps draw in one line inside a
fixed box (a tab, a rail item, a short button) has a width budget, measured for the 360 dp
phone (the narrowest we support) at the label's font size. Every language must fit it.

Width: a Latin letter counts 1, a capital 1.2, an Indic letter (Devanagari, Bengali, Telugu,
Tamil, Kannada) 1.35 (they are drawn wider at the same size), a combining sign or joiner 0
(it sits on its letter). Budgets are those units at the label's size in its box, from the
layout (see each entry's note).

Not covered by this check: labels that wrap (they grow the box instead), text of data
(kitchen and dish names), and the layout of whole screens; QA screenshots cover those.
Stdlib only (the Repo checks job has Python and nothing else).
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESSAGES = ROOT / "packages" / "i18n" / "messages"

# key (or key prefix ending in "."): (budget, where it is drawn)
BUDGETS: dict[str, tuple[float, str]] = {
    "tabs.": (13, "customer app tab bar: 4 tabs across 360 dp, caption size, one line"),
    "rider.tabs.": (14, "delivery app tab bar: 3 tabs across 360 dp, small size, one line"),
    "partner.rail.": (11, "kitchen app rail: 72 dp items (phone: 4 tabs across 360 dp), caption size, one line"),
    "partner.orders.new": (12, "kitchen app phone board tab (3 across 360 dp, with a count badge), label size"),
    "partner.orders.preparing_short": (12, "kitchen app phone board tab"),
    "partner.orders.ready_short": (12, "kitchen app phone board tab"),
    "partner.orders.busy_short": (16, "kitchen app header button on a small tablet, one line"),
    "partner.orders.pause_short": (16, "kitchen app header button on a small tablet, one line"),
}

INDIC = ("DEVANAGARI", "BENGALI", "TELUGU", "TAMIL", "KANNADA")


def width(text: str) -> float:
    w = 0.0
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in ("Mn", "Me", "Cf"):
            continue
        name = unicodedata.name(ch, "")
        if cat == "Mc":
            w += 0.35  # a spacing vowel sign: part of its letter's cluster, a little wider
        elif name.startswith(INDIC):
            w += 1.35
        elif ch.isupper():
            w += 1.2
        elif ch == " ":
            w += 0.5
        else:
            w += 1.0
    return w


def flat(o: dict, p: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in o.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{p}{k}."))
        elif isinstance(v, str):
            out[f"{p}{k}"] = v
    return out


def budget(key: str) -> tuple[float, str] | None:
    if key in BUDGETS:
        return BUDGETS[key]
    for prefix, b in BUDGETS.items():
        if prefix.endswith(".") and key.startswith(prefix) and "." not in key[len(prefix):]:
            return b
    return None


def problems(directory: Path) -> list[str]:
    out = []
    checked = 0
    for file in sorted(directory.glob("*.json")):
        for key, text in flat(json.loads(file.read_text(encoding="utf-8"))).items():
            b = budget(key)
            if not b:
                continue
            checked += 1
            if width(text) > b[0]:
                out.append(f"{file.stem}: {key} = {text!r} is {width(text):.1f} wide, the budget is {b[0]} ({b[1]})")
    if not checked:
        out.append("no budgeted keys found: the BUDGETS list no longer matches the catalog")
    return out


def self_test() -> None:
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(MESSAGES / "en.json", Path(tmp) / "en.json")
        long = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))
        long["tabs"]["home"] = "A much too long home tab label"
        (Path(tmp) / "xx.json").write_text(json.dumps(long), encoding="utf-8")
        found = problems(Path(tmp))
        assert any(p.startswith("xx: tabs.home") for p in found), found
        assert not any(p.startswith("en:") for p in found), found
    assert width("హోమ్") < width("హోమ్ పేజీ") and width("ab") == 2
    print("self-test ok: a label over its budget fails")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    if ap.parse_args().self_test:
        self_test()
        return
    found = problems(MESSAGES)
    for p in found:
        print("FAIL", p)
    if found:
        sys.exit(1)
    print(f"app label widths ok ({len(BUDGETS)} budgets, every language)")


if __name__ == "__main__":
    main()
