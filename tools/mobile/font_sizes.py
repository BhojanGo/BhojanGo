"""Font sizes on screen in the Expo apps, per app and screen (round 6 type scale).

Android's view hierarchy (uiautomator dump, Maestro) has text and bounds but no
font size, so the apps report their own: with EXPO_PUBLIC_FONT_AUDIT=1 the type
tokens (packages/mobile-core/src/ui/type.ts) record every size a screen renders
and log one line per screen, e.g.

    FONT_AUDIT /orders 12,14,15,18,30
    FONT_AUDIT /restaurant/42 12,14,15,16,18,22,30

The flag is dev-only and costs nothing when off (Expo inlines EXPO_PUBLIC_* at
bundle time, so the recording branch is dead code in every other build).

How to collect them (one app at a time, on the emulator):

    # 1. start Metro with the flag (it is read when Metro bundles: -c clears the cache)
    cd apps/customer
    EXPO_PUBLIC_FONT_AUDIT=1 npx expo start -c 2>&1 | tee ../../font-customer.log
    # 2. open the app on emulator-5554 and walk it: run the read-only Maestro flows
    #    (maestro --device emulator-5554 test .maestro/<flow>.yaml), or tap through by hand
    # 3. stop Metro, then
    python tools/mobile/font_sizes.py customer=font-customer.log rider=font-rider.log partner=font-partner.log

Metro prints the lines as " LOG  FONT_AUDIT ..."; `adb -s emulator-5554 logcat -s
ReactNativeJS` shows the same lines from a dev build, and either log works here.
Each FILE may be "app=path" (to name the app) or a bare path (named after the file).

Output: per app, every screen with its sizes, then the union of sizes; any size
that is not on the scale (12 14 15 16 17 18 22 30 44) or is under 14 without being
the caption size is flagged and the exit status is 1. --json prints the same as JSON.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# The phone column of the scale (packages/mobile-core/src/ui/type.ts TYPE_SCALE).
SCALE = {44: "display", 30: "h1", 22: "h2", 18: "h3", 17: "bodyLg", 16: "body", 15: "label", 14: "small", 12: "caption"}
CAPTION = 12
LINE = re.compile(r"FONT_AUDIT\s+(\S+)\s+([\d.,]*)")


def parse(text: str) -> dict[str, set[float]]:
    """Route -> every size seen on it (a screen may log more than once as data arrives)."""
    routes: dict[str, set[float]] = {}
    for m in LINE.finditer(text):
        sizes = {float(x) for x in m.group(2).split(",") if x}
        routes.setdefault(m.group(1), set()).update(sizes)
    return routes


def problems(sizes: set[float]) -> list[str]:
    out = []
    for s in sorted(sizes):
        if s not in SCALE:
            out.append(f"{fmt(s)} is not on the type scale")
        elif s < 14 and s != CAPTION:
            out.append(f"{fmt(s)} is under 14 and not the caption")
    return out


def fmt(s: float) -> str:
    return str(int(s)) if s == int(s) else str(s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", help='Metro or logcat logs: "app=path" or a path')
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)

    report: dict[str, dict[str, list[float]]] = {}
    for spec in args.files:
        app, _, path = spec.partition("=") if "=" in spec else (pathlib.Path(spec).stem, "", spec)
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        for route, sizes in parse(text).items():
            report.setdefault(app, {}).setdefault(route, [])
            report[app][route] = sorted(set(report[app][route]) | sizes)

    bad = 0
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        bad = sum(len(problems(set(s))) for routes in report.values() for s in routes.values())
        return 1 if bad else 0

    if not report:
        print("no FONT_AUDIT lines found: was Metro started with EXPO_PUBLIC_FONT_AUDIT=1 (and -c)?", file=sys.stderr)
        return 2
    for app in sorted(report):
        routes = report[app]
        print(f"## {app} ({len(routes)} screens)")
        width = max(len(r) for r in routes)
        union: set[float] = set()
        for route in sorted(routes):
            sizes = set(routes[route])
            union |= sizes
            roles = " ".join(f"{fmt(s)}:{SCALE.get(s, '??')}" for s in sorted(sizes))
            print(f"  {route.ljust(width)}  {roles}")
            for p in problems(sizes):
                bad += 1
                print(f"  {' ' * width}  !! {p}")
        print(f"  all sizes: {', '.join(fmt(s) for s in sorted(union))}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
