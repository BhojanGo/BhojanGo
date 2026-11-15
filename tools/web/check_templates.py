"""Fail if the website's templates name a seeded city, state or country
(docs/design/web/WebDataRules.html: launching a city is an admin action in
Markets, so no page may know a place by name).

    python tools/web/check_templates.py          (make ci: ci-web-data)

Checks apps/web/src (code, comments included: a comment naming a city is how a
hard-coded one starts) and the website's messages (packages/i18n/messages). The
names come from the seed (tools/seed/data.py), so a new seeded place is checked
too. Whole words only: "Indian" is a cuisine, "India" is a country.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "seed"))
import data  # noqa: E402

SCAN = [(ROOT / "apps" / "web" / "src", ("*.ts", "*.tsx", "*.js", "*.mjs", "*.css")),
        (ROOT / "packages" / "i18n" / "messages", ("*.json",))]
# Photo credits are other people's photo titles (data generated from LICENSES.md).
SKIP = {ROOT / "apps" / "web" / "src" / "content" / "photo-credits.json"}


def place_names() -> set[str]:
    names: set[str] = set()
    for c in data.COUNTRIES:
        names.add(c["name"])
        for r in c["regions"]:
            names.add(r["name"])
            for city in r["cities"]:
                names.add(city["name"])
    for m in data.MARKETS:
        names.update(filter(None, (m.get("country_name"), m.get("state"), m.get("city"))))
    return names


def main() -> int:
    names = sorted(place_names(), key=len, reverse=True)
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n in names) + r")(?![\w])")
    problems = []
    for base, globs in SCAN:
        for g in globs:
            for path in base.rglob(g):
                if path in SKIP or "node_modules" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8")
                if path.suffix == ".json":
                    json.loads(text)  # valid JSON too
                for n, line in enumerate(text.splitlines(), 1):
                    for m in pattern.finditer(line):
                        problems.append(f"{path.relative_to(ROOT)}:{n}: \"{m.group(1)}\" (a seeded place; read it from Markets data)")
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} place name(s) in website templates. Cities, states and countries come from data.")
        return 1
    print(f"website templates name no seeded place ({len(names)} names checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
