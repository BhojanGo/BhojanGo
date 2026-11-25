"""R41: the validation sweep's index: one row per page or screen, user and width (web, admin) or app screen.

    python tools/sweep/index.py <sweep dir> [maestro results file ...]

<sweep dir> holds sweep-web.json (tools/sweep/sweep_web.py) and apps/<app>/<shot>.png (Maestro screenshots copied
there); the results files are the Maestro runner's output ("PASS customer/flow #1", "FAIL ..."). A screen passes
when every flow that opens it passed (its last run counts). Writes <sweep dir>/index.md.
"""
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    out, logs = sys.argv[1], sys.argv[2:]
    web = json.load(open(os.path.join(out, "sweep-web.json"), encoding="utf-8"))
    apps = json.load(open(os.path.join(HERE, "apps.json"), encoding="utf-8"))
    flow_result: dict[str, str] = {}
    for path in logs:
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"^(PASS|FAIL) (\w+)/([\w-]+) #\d+(?::\s*(.*))?", line.strip())
            if m:
                flow_result[f"{m.group(2)}/{m.group(3)}"] = m.group(1) + (f": {m.group(4)[:120]}" if m.group(4) else "")
    rows = []
    for r in web:
        rows.append((r["app"], r["page"], r.get("route") or "", "US" if r["user"] == "us" else "India", f"{r['width']} px",
                     ", ".join(r.get("checks", [])), r["result"] + (f": {r['why']}" if r.get("why") else ""),
                     f"web/{r['screenshot']}" if r.get("screenshot") else ""))
    for app, screens in apps.items():
        if app.startswith("_"):
            continue
        for sc in screens:
            results = [flow_result.get(f"{app}/{f}", "NOT RUN") for f in sc["flows"]]
            failed = [f"{f}: {res}" for f, res in zip(sc["flows"], results) if not res.startswith("PASS")]
            shots = [f"apps/{app}/{s}.png" for s in sc["shots"] if os.path.exists(os.path.join(out, "apps", app, f"{s}.png"))]
            users = "US + India" if any(f.endswith(("-us", "-in")) or f.startswith(("r38", "r39")) for f in sc["flows"]) else "seed user"
            rows.append((f"{app} app", sc["screen"], "", users, "emulator",
                         "flow passes: " + ", ".join(sc["flows"]),
                         "FAIL: " + "; ".join(failed) if failed else "PASS", " ".join(shots)))
    total = Counter(r[6].split(":")[0] for r in rows)
    lines = ["# Validation sweep (round 41)", "",
             f"{len(rows)} rows: **{total.get('PASS', 0)} PASS**, **{total.get('FAIL', 0)} FAIL**, {total.get('SKIP', 0)} SKIP "
             "(SKIP: no such item exists for that user on a fresh seed).", "",
             "Web and admin rows: `tools/sweep/sweep_web.py` (every page, a US and an India user, 1440 and 390 px). "
             "App rows: the Maestro flows that open the screen on the Android emulator (their own assertions, plus the "
             "sweep checks in the `r41-sweep*` flows).", "",
             "| App | Page | Route | User | Width | Checks | Result | Screenshot |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    open(os.path.join(out, "index.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(rows)} rows", dict(total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
