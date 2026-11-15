"""Fail if the website's or the apps' code names a seeded city, state or country,
or (apps) hard-codes a country's money, phone code, locale or distance unit
(docs/design/web/WebDataRules.html: launching a city is an admin action in
Markets, so no page or screen may know a place by name).

    python tools/web/check_templates.py          (make ci: ci-web-data)

Website: apps/web/src (code, comments included: a comment naming a city is how a
hard-coded one starts) and the messages (packages/i18n/messages). The names come
from the seed (tools/seed/data.py), so a new seeded place is checked too. Whole
words only: "Indian" is a cuisine, "India" is a country.

Apps (B4): apps/customer, apps/rider, apps/partner and packages/mobile-core
(not node_modules, generated android/ios, .expo or the Maestro flows) get the
place check and these country rules, because every one of them is Markets data
(countries: currency, locales, phone_code, distance_unit):

  currency symbol   "₹", "€", "£", "¥", or "$" used as money ("$5", "$${x}", "$")
  currency code     INR, USD, ... (the seed's currencies and a few common ones)
  country code      "IN", "US", ... as a string (the seed's countries)
  phone prefix      "+91", `+1${n}`, "IN +91" (not "+10 min")
  locale tag        "en-US", "hi-IN" (format with the country's formatLocale)
  distance unit     "km" / "mi" as strings, or after a number ("2.1 km", `${d} mi`)

Format with mobile-core's useI18n() (money, distance, date) and read the rest
from useCountry(). A line that really needs one (a regex backreference, the
km/mi conversion inside the formatter) says why with a marker on that line or
the line above:   // data-ok: <reason>
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "seed"))
import data  # noqa: E402

SCAN = [(ROOT / "apps" / "web" / "src", ("*.ts", "*.tsx", "*.js", "*.mjs", "*.css")),
        (ROOT / "packages" / "i18n" / "messages", ("*.json",))]
APPS = [ROOT / "apps" / "customer", ROOT / "apps" / "rider", ROOT / "apps" / "partner",
        ROOT / "packages" / "mobile-core"]
APP_GLOBS = ("*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs")
# Generated or not UI code: dependencies, native projects, Expo's cache, e2e flows, test fixtures.
APP_SKIP_DIRS = {"node_modules", "android", "ios", ".expo", ".maestro", "dist", "build", "test", "__tests__"}
# Photo credits are other people's photo titles (data generated from LICENSES.md).
SKIP = {ROOT / "apps" / "web" / "src" / "content" / "photo-credits.json"}

MARKER = re.compile(r"data-ok:\s*\S")


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


def country_rules() -> list[tuple[str, re.Pattern[str]]]:
    """(what, pattern) for hard-coded country values in app code."""
    currencies = {c["currency"] for c in data.COUNTRIES} | {"INR", "USD", "EUR", "GBP", "NZD", "AUD", "CAD", "SGD", "AED"}
    codes = {c["code"] for c in data.COUNTRIES} | {"NZ", "GB", "AU", "CA"}
    q = r"""["'`]"""
    return [
        ("currency symbol", re.compile(r"[₹€£¥]")),
        # "$5", "$12.50", `$${amount}`, a lone "$" string. Not `${x}` (a template) or "$1" in .replace().
        ("currency symbol", re.compile(r"(?<![\w$])\$(?=\d)|\$\$\{|" + q + r"\$" + q)),
        ("currency code", re.compile(r"(?<![\w-])(" + "|".join(sorted(currencies)) + r")(?![\w-])")),
        ("country code", re.compile(q + r"(" + "|".join(sorted(codes)) + r")" + q)),
        # "+91", `+1${n}`, "+91 98480 21234"; not "+10 min" (a quantity).
        ("phone prefix", re.compile(r"(?<![\w)\]+])\+\d{1,3}(?!\d)(?=[\"'`]|\$\{|\s?\d)")),
        ("locale tag", re.compile(q + r"[a-z]{2,3}-[A-Z]{2}" + q)),
        ("distance unit", re.compile(q + r"(km|mi|miles|kilometres|kilometers)" + q
                                     + r"|(?:\d|\})\s?(km|mi|miles)\b|>\s*(km|mi|miles)\s*<")),
    ]


def app_files():
    """App source files, never walking into a skipped directory (node_modules is huge)."""
    for base in APPS:
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in APP_SKIP_DIRS)
            for f in sorted(files):
                path = Path(root) / f
                if any(path.match(g) for g in APP_GLOBS) and not f.endswith(".config.js") and ".test." not in f:
                    yield path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # "₹" on a Windows console
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

    rules = country_rules()
    app_problems = []
    checked = 0
    for path in app_files():
        checked += 1
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            for m in pattern.finditer(line):
                app_problems.append(f"{path.relative_to(ROOT)}:{n}: \"{m.group(1)}\" (a seeded place; read it from Markets data)")
            if MARKER.search(line) or (n > 1 and MARKER.search(lines[n - 2]) and lines[n - 2].strip().startswith(("//", "/*", "*", "{/*"))):
                continue
            for what, rule in rules:
                for m in rule.finditer(line):
                    if m.group(0) == "$" and ".replace(" in line:
                        continue  # "$1" is a regex backreference there, not money
                    app_problems.append(f"{path.relative_to(ROOT)}:{n}: \"{m.group(0)}\" ({what}; use useI18n()/useCountry() "
                                        "from @bhojango/mobile-core, or mark a legitimate use with // data-ok: <reason>)")
    if problems or app_problems:
        print("\n".join(problems + app_problems))
        if problems:
            print(f"\n{len(problems)} place name(s) in website templates. Cities, states and countries come from data.")
        if app_problems:
            print(f"\n{len(app_problems)} hard-coded place or country value(s) in the apps. They come from Markets data.")
        return 1
    print(f"website templates name no seeded place ({len(names)} names checked); "
          f"apps hard-code no place or country value ({checked} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
