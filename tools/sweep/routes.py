"""R42: every route, read from the code, and the functional spec that covers it.

Website and admin: each page.tsx under apps/<app>/src/app (route groups "(x)" dropped). Customer, restaurant and
delivery-partner apps: each screen file under apps/<app>/app (expo-router: the files are the navigator), without
layouts and "+" special files.

    python tools/sweep/routes.py            # the list, and what has no spec or isn't in the round 41 sweep
    python tools/sweep/routes.py --check    # CI (Repo checks): exit 1 when a route has no functional spec, a spec
                                            # names a route that doesn't exist, or a spec lacks a required kind

A spec is tools/sweep/functional/<app>/<name>.json (README.md there). Standard library only.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPECS = ROOT / "tools" / "sweep" / "functional"
WEB_APPS = {"web": "apps/web/src/app", "admin": "apps/admin/src/app"}
NATIVE_APPS = {"customer": "apps/customer/app", "partner": "apps/partner/app", "rider": "apps/rider/app"}
APP_NAMES = {"web": "website", "admin": "admin", "customer": "customer app", "partner": "restaurant app",
             "rider": "delivery partner app"}
# Each page's spec has at least one function of each of these kinds, or says why the kind doesn't apply ({"kind":
# "permission", "na": "a public page: anyone may open it"}). "action" is any of ACTIONS.
ACTIONS = {"button", "link", "form", "filter", "toggle", "navigation"}
REQUIRED = ("action", "empty", "error", "permission")
KINDS = ACTIONS | {"empty", "error", "permission", "number", "display"}


def web_routes(app: str) -> list[str]:
    base = ROOT / WEB_APPS[app]
    out = []
    for p in base.rglob("page.tsx"):
        parts = [s for s in p.parent.relative_to(base).parts if not (s.startswith("(") and s.endswith(")"))]
        out.append("/" + "/".join(parts))
    return sorted(set(out))


def native_routes(app: str) -> list[str]:
    base = ROOT / NATIVE_APPS[app]
    out = []
    for p in base.rglob("*.tsx"):
        if p.name.startswith(("_layout", "+")):
            continue
        out.append(p.relative_to(base).with_suffix("").as_posix())
    return sorted(out)


def all_routes() -> dict[str, list[str]]:
    return {**{a: web_routes(a) for a in WEB_APPS}, **{a: native_routes(a) for a in NATIVE_APPS}}


def specs() -> dict[tuple[str, str], tuple[Path, dict]]:
    found = {}
    for p in sorted(SPECS.glob("*/*.json")):
        spec = json.loads(p.read_text(encoding="utf-8"))
        found[(spec.get("app", p.parent.name), spec.get("route", ""))] = (p, spec)
    return found


def spec_problems(path: Path, spec: dict) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    problems = []
    fns = spec.get("functions") or []
    if not fns:
        return [f"{rel}: no functions"]
    ids = [f.get("id") for f in fns]
    if len(set(ids)) != len(ids) or None in ids:
        problems.append(f"{rel}: every function needs a unique id")
    for f in fns:
        kind = f.get("kind")
        if kind not in KINDS and not (kind == "action" and "na" in f):
            problems.append(f"{rel}: {f.get('id')}: kind {kind!r} is not one of {sorted(KINDS)}")
        if "na" in f:
            continue
        for field in ("action", "expected", "verify"):
            if not f.get(field):
                problems.append(f"{rel}: {f.get('id')}: no {field}")
        if not (f.get("run") or f.get("maestro") or f.get("test")):
            problems.append(f"{rel}: {f.get('id')}: says nothing that runs it (run, maestro or test)")
    have = {("action" if f.get("kind") in ACTIONS else f.get("kind")) for f in fns}
    for need in REQUIRED:
        if need not in have:
            problems.append(f"{rel}: no {need} function (or one with \"na\": why it doesn't apply)")
    return problems


def r41_swept() -> dict[str, set[str]]:
    """The routes the round 41 sweep opened: its page lists (sweep_web.py) and app screens (apps.json)."""
    tree = ast.parse((ROOT / "tools/sweep/sweep_web.py").read_text(encoding="utf-8"))
    lists = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("WEB_PAGES", "ADMIN_PAGES"):
            lists[node.targets[0].id] = {t[0] for t in ast.literal_eval(node.value)}
    apps = json.loads((ROOT / "tools/sweep/apps.json").read_text(encoding="utf-8"))
    return {"web": lists.get("WEB_PAGES", set()), "admin": lists.get("ADMIN_PAGES", set()),
            **{a: {s["screen"] for s in apps.get(a, [])} for a in NATIVE_APPS}}


def main(argv: list[str]) -> int:
    routes, have, swept = all_routes(), specs(), r41_swept()
    problems: list[str] = []
    for app, rs in routes.items():
        for r in rs:
            if (app, r) not in have:
                problems.append(f"{APP_NAMES[app]} {r}: no functional spec in tools/sweep/functional/{app}/")
    for (app, r), (p, spec) in have.items():
        if r not in routes.get(app, []):
            problems.append(f"{p.relative_to(ROOT).as_posix()}: {app} {r} is not a route in the code")
        problems += spec_problems(p, spec)
    if "--check" not in argv:
        for app, rs in routes.items():
            print(f"{APP_NAMES[app]}: {len(rs)} routes")
            for r in rs:
                print(f"    {r}{'' if r in swept[app] else '   (not in the round 41 sweep)'}")
        missed = {a: sorted(set(rs) - swept[a]) for a, rs in routes.items()}
        extra = {a: sorted(swept[a] - set(rs)) for a, rs in routes.items()}
        print("missed by round 41:", {a: m for a, m in missed.items() if m} or "none")
        print("round 41 names no longer in the code:", {a: m for a, m in extra.items() if m} or "none")
    total = sum(map(len, routes.values()))
    print(f"{total} routes; {sum(1 for k in have if k[1] in routes.get(k[0], []))} with a spec; {len(problems)} problem(s)")
    for p in problems:
        print("  -", p)
    return 1 if problems and "--check" in argv else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
