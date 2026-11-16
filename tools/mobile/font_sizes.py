"""Font sizes on screen in the Expo apps, per app and screen (round 8 fluid type scale).

Android's view hierarchy (uiautomator dump, Maestro) has text and bounds but no
font size, so the apps report their own: with EXPO_PUBLIC_FONT_AUDIT=1 the type
tokens (packages/mobile-core/src/ui/type.ts) record every role and size a screen
renders and log one line per screen, e.g.

    FONT_AUDIT /orders caption:12,small:13,label:14,h3:17,h1:28
    FONT_AUDIT /restaurant/42 caption:12,small:13,label:14,body:15,h3:17,h2:22,h1:28

(older builds logged bare sizes, "12,14,15,18,30"; those are still read). The
sizes are fluid: each role runs from its min on a 360 dp screen to its max at
1440 dp (the screen's shorter side), so a phone logs about the min and a tablet
sizes in between. They are the sizes before the phone's own font setting, which
React Native applies on top.

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

Output: per app, every screen with its roles and sizes, then the union of sizes.
A size outside its role's [min, max] (display 36-52, h1 28-36, h2 22-28, h3 17-20,
bodyLg 16-18, body 15-16, label 14-15, small 13-14, caption 12), a bare size that
is in no role's range, or anything under 13 that is not the caption is flagged and
the exit status is 1. --json prints the same as JSON.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# The scale (packages/mobile-core/src/ui/type.ts TYPE_SCALE): each role's [min, max] in dp.
SCALE = {"display": (36, 52), "h1": (28, 36), "h2": (22, 28), "h3": (17, 20), "bodyLg": (16, 18),
         "body": (15, 16), "label": (14, 15), "small": (13, 14), "caption": (12, 12)}
CAPTION = 12
MIN_READABLE = 13
LINE = re.compile(r"FONT_AUDIT\s+(\S+)\s+([\w.:,]*)")

# One rendered size: (role or None for an older bare-size line, size).
Seen = tuple[str | None, float]


def parse(text: str) -> dict[str, set[Seen]]:
    """Route -> every (role, size) seen on it (a screen may log more than once as data arrives)."""
    routes: dict[str, set[Seen]] = {}
    for m in LINE.finditer(text):
        seen: set[Seen] = set()
        for x in (x for x in m.group(2).split(",") if x):
            role, _, size = x.rpartition(":")
            seen.add((role or None, float(size)))
        routes.setdefault(m.group(1), set()).update(seen)
    return routes


def problems(seen: set[Seen]) -> list[str]:
    out = []
    for role, s in sorted(seen, key=lambda x: (x[1], x[0] or "")):
        if role is not None and role not in SCALE:
            out.append(f"{role}:{fmt(s)} is not a type role")
        elif role is not None and not SCALE[role][0] <= s <= SCALE[role][1]:
            lo, hi = SCALE[role]
            out.append(f"{role} {fmt(s)} is outside {role}'s {fmt(lo)}-{fmt(hi)}")
        elif role is None and not any(lo <= s <= hi for lo, hi in SCALE.values()):
            out.append(f"{fmt(s)} is not on the type scale")
        elif s < MIN_READABLE and not (s == CAPTION and role in (None, "caption")):
            out.append(f"{fmt(s)} is under {MIN_READABLE} and not the caption")
    return out


def fmt(s: float) -> str:
    return str(int(s)) if s == int(s) else str(s)


def label(seen: Seen) -> str:
    role, s = seen
    return f"{role}:{fmt(s)}" if role else f"{fmt(s)}:??"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", help='Metro or logcat logs: "app=path" or a path')
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)

    report: dict[str, dict[str, list[Seen]]] = {}
    for spec in args.files:
        app, _, path = spec.partition("=") if "=" in spec else (pathlib.Path(spec).stem, "", spec)
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        for route, sizes in parse(text).items():
            report.setdefault(app, {}).setdefault(route, [])
            report[app][route] = sorted(set(report[app][route]) | sizes, key=lambda x: (x[1], x[0] or ""))

    bad = 0
    if args.json:
        print(json.dumps({a: {r: [label(x) for x in v] for r, v in routes.items()} for a, routes in report.items()}, indent=2, sort_keys=True))
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
            union |= {s for _, s in sizes}
            roles = " ".join(label(x) for x in routes[route])
            print(f"  {route.ljust(width)}  {roles}")
            for p in problems(sizes):
                bad += 1
                print(f"  {' ' * width}  !! {p}")
        print(f"  all sizes: {', '.join(fmt(s) for s in sorted(union))}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
