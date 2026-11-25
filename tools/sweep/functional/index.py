"""R42: the functional validation report, OUT/index.md: one row per page, function and user.

    python tools/sweep/functional/index.py <OUT> [maestro results file ...]

Website and admin rows: OUT/functional-up.json and OUT/functional-down.json (run_web.py). App rows: each screen
function's Maestro flow (apps.py), PASS/FAIL from the runner's results lines ("PASS customer/r42-bill-in #1"), its
screenshots from OUT/apps/<app>/*.png when copied there. A function with no flow is NOT RUN (never counted as passed).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import framework as fw  # noqa: E402
import admin  # noqa: E402,F401
import apps  # noqa: E402,F401
import web  # noqa: E402,F401

APP = {"web": "website", "admin": "admin", "customer": "customer app", "partner": "restaurant app", "rider": "delivery partner app"}
MONEY_KINDS = {"number"}


def cell(v: object) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def main() -> int:
    out, logs = sys.argv[1], sys.argv[2:]
    rows: list[dict] = []
    for phase in ("up", "down"):
        p = os.path.join(out, f"functional-{phase}.json")
        if os.path.exists(p):
            rows += json.load(open(p, encoding="utf-8"))
    flow: dict[str, str] = {}
    for path in logs:
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"^(PASS|FAIL) (\w+)/([\w./-]+?) #\d+(?::\s*(.*))?$", line.strip())
            if m:
                flow[f"{m.group(2)}/{m.group(3)}"] = m.group(1) + (f": {m.group(4)[:140]}" if m.group(4) else "")
    for f in fw.REGISTRY:
        if f.run is not None:
            continue
        res = flow.get(f"{f.app}/{f.maestro}", "NOT RUN") if f.maestro else "NOT RUN: no flow yet"
        shots_dir = os.path.join(out, "apps", f.app)
        shots = sorted(x for x in os.listdir(shots_dir) if f.maestro and x.startswith(f.maestro.split("/")[-1].replace("r42-", "r42-")[:6])) \
            if os.path.isdir(shots_dir) else []
        for user in f.users:
            rows.append({"app": f.app, "page": f.route, "function": f.id, "kind": f.kind, "user": user, "expected": f.expected,
                         "actual": f"Maestro {f.maestro}.yaml: {res}" if f.maestro else "not automated yet",
                         "result": "PASS" if res.startswith("PASS") else ("FAIL" if res.startswith("FAIL") else "NOT RUN"),
                         "screenshots": [f"apps/{f.app}/{s}" for s in shots[:2]]})
    total = Counter(r["result"] for r in rows)
    pages = {(r["app"], r["page"]) for r in rows}
    numbers = sum(1 for r in rows if r["kind"] in MONEY_KINDS)
    lines = ["# Functional validation (round 42)", "",
             f"{len(pages)} pages and screens · {len({(r['app'], r['page'], r['function']) for r in rows})} functions · "
             f"{len(rows)} rows (function × user) · {numbers} number checks", "",
             f"**{total.get('PASS', 0)} PASS** · **{total.get('FAIL', 0)} FAIL** · {total.get('NOT RUN', 0)} NOT RUN", "",
             "Specs: `tools/sweep/functional/<app>/<route>.json` (action → expected → how it's verified). Website and admin: "
             "`run_web.py` (Playwright, API and database on a test stack; then every page with core-api stopped). Apps: the "
             "Maestro flow named in the spec. Screenshots before and after each action that changes data.", "",
             "| App | Page | Function | User | Expected | Actual | Result | Screenshot |", "|---|---|---|---|---|---|---|---|"]
    order = {"FAIL": 0, "NOT RUN": 1, "PASS": 2}
    for r in sorted(rows, key=lambda r: (list(APP).index(r["app"]), r["page"], order.get(r["result"], 3), r["function"], r["user"])):
        shots = " ".join(r.get("screenshots") or [])
        lines.append("| " + " | ".join(cell(c) for c in (APP[r["app"]], r["page"], r["function"], r["user"].upper(), r["expected"],
                                                          r["actual"], r["result"], shots)) + " |")
    open(os.path.join(out, "index.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(rows)} rows, {len(pages)} pages", dict(total), f"{numbers} number checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
