"""R42: the functional spec of every page and screen, one JSON file per route, written from the functions themselves
(web.py, admin.py, apps.py), so the spec and what runs can't drift apart.

    python tools/sweep/functional/specs.py           # (re)write tools/sweep/functional/<app>/<route>.json
    python tools/sweep/functional/specs.py --check   # CI: the files match the functions (then routes.py --check)

Each file: {"app", "route", "functions": [{"id", "kind", "users", "action", "expected", "verify", "run"}...]}, where
"run" says what does it: "playwright: run_web.py" (phase up or "api down") or "maestro: apps/<app>/.maestro/<flow>.yaml",
and a kind that doesn't apply is {"kind", "na": why}. Standard library only (no browser needed to import the functions).
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import framework as fw  # noqa: E402
import admin  # noqa: E402,F401
import apps  # noqa: E402,F401
import web  # noqa: E402,F401

FLOWS = {"customer": "apps/customer/.maestro", "partner": "apps/partner/.maestro", "rider": "apps/rider/.maestro"}


def slug(route: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", route.lower()).strip("-") or "root"


def build() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in fw.REGISTRY:
        spec = out.setdefault(f"{f.app}/{slug(f.route)}.json", {"app": f.app, "route": f.route, "functions": []})
        run = (f"maestro: {FLOWS[f.app]}/{f.maestro}.yaml" if f.maestro else "not automated yet (NOT RUN)") if f.run is None else \
            ("playwright: tools/sweep/functional/run_web.py, phase down (core-api stopped)" if f.down else
             "playwright + API: tools/sweep/functional/run_web.py")
        entry = {"id": f.id, "kind": f.kind, "users": list(f.users), "action": f.action, "expected": f.expected, "verify": f.verify, "run": run}
        if f.run is None:
            entry["maestro" if f.maestro else "test"] = f.maestro or "none"
        else:
            entry["test"] = f"{f.app}{f.route}#{f.id}"
        spec["functions"].append(entry)
    for n in fw.NA:
        spec = out.setdefault(f"{n['app']}/{slug(n['route'])}.json", {"app": n["app"], "route": n["route"], "functions": []})
        spec["functions"].append({"id": f"na-{n['kind']}", "kind": n["kind"], "na": n["na"]})
    return out


def main(argv: list[str]) -> int:
    specs = build()
    stale = []
    for rel, spec in sorted(specs.items()):
        path = os.path.join(HERE, rel)
        text = json.dumps(spec, indent=1, ensure_ascii=False) + "\n"
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old != text:
            stale.append(rel)
            if "--check" not in argv:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "w", encoding="utf-8", newline="\n").write(text)
    known = set(specs)
    extra = [os.path.relpath(os.path.join(d, f), HERE).replace(os.sep, "/") for d, _, fs in os.walk(HERE) for f in fs
             if f.endswith(".json") and os.path.basename(d) in FLOWS.keys() | {"web", "admin"}]
    extra = [e for e in extra if e not in known]
    if "--check" in argv:
        for rel in stale + extra:
            print(f"out of date: tools/sweep/functional/{rel} (run python tools/sweep/functional/specs.py)")
        return 1 if stale or extra else 0
    for e in extra:
        os.remove(os.path.join(HERE, e))
    fns = sum(len(s["functions"]) for s in specs.values())
    print(f"{len(specs)} spec files, {fns} entries ({len(stale)} written, {len(extra)} removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
