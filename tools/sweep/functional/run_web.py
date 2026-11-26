"""R42: run the website and admin page functions (web.py, admin.py) as the US and India users, on a local test stack.

    tools/sweep/functional/run.sh            # both phases: everything, then core-api stopped for the "API down" checks
    PHASE=up|down ONLY=<regex on app+route+id> python run_web.py   (inside the Playwright image, like sweep_web.py)

Writes OUT/functional-<phase>.json (one row per function and user) and screenshots OUT/<app>/*.png.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402

PHASE = os.environ.get("PHASE", "up")
if PHASE == "up":
    ensure_safe_api("http://core-api:8001")  # a local stack on a test database (core-api is stopped in "down")

import framework as fw  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import admin  # noqa: E402,F401  (registers the admin functions)
import apps  # noqa: E402,F401  (the app screens: Maestro flows, and the API checks run here)
import web  # noqa: E402,F401  (registers the website functions)
import r43  # noqa: E402,F401  (R43: menu editing where customers and admins see it)

OUT = os.environ.get("OUT", "/out")
ONLY = re.compile(os.environ.get("ONLY", ".*"))


def main() -> int:
    for port, target in fw.FORWARD.items():
        fw.forward(port, target)
    os.makedirs(f"{OUT}/sessions", exist_ok=True)
    saved = f"{OUT}/sessions/states.json"
    if PHASE == "down" and os.path.exists(saved):
        fw.sessions.states = {tuple(k.split("|", 1)): v for k, v in json.load(open(saved, encoding="utf-8")).items()}
    rows: list[dict] = []
    todo = [f for f in fw.REGISTRY if f.run is not None and f.down == (PHASE == "down") and ONLY.search(f"{f.app}{f.route}#{f.id}")]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        if PHASE == "up":
            web.setup()
        for f in todo:
            for user in f.users:
                started = time.time()
                first = None  # R44: a failure is tried once more; a pass then is reported as FLAKY with the first reason
                for attempt in (1, 2):
                    t = fw.T(browser=browser, user=user, out=OUT, fn=f)
                    try:
                        actual = f.run(t) or "as expected"
                        errors = t.vars.get("_errors") or []
                        if errors:
                            raise fw.Fail(f"page error: {errors[0]}")
                        result = "PASS"
                    except Exception as e:  # noqa: BLE001 - a function that fails is a FAIL row with its reason
                        actual = f"{type(e).__name__}: {e}" if isinstance(e, fw.Fail) else f"{type(e).__name__}: {str(e)[:240]}"
                        if not isinstance(e, fw.Fail):
                            traceback.print_exc(limit=2)
                        result = "FAIL"
                        try:
                            if t.page is not None:
                                t.shot("fail")
                        except Exception:  # noqa: BLE001
                            pass
                    finally:
                        t.close()
                    if result == "PASS" or attempt == 2:
                        break
                    first = str(actual)[:160]
                if first and result == "PASS":
                    actual = f"{actual} — FLAKY: passed on the second try (first: {first})"
                elif first:
                    actual = f"{actual} (both tries)"
                rows.append({"app": f.app, "page": f.route, "function": f.id, "kind": f.kind, "user": user,
                             "action": f.action, "expected": f.expected, "verify": f.verify, "actual": str(actual)[:400],
                             "result": result, "screenshots": t.shots, "seconds": round(time.time() - started, 1)})
                print(result, f.app, f.route, f.id, user, str(actual)[:160], flush=True)
        if PHASE == "up":
            if fw.sessions.fresh_email:  # R44: the new customer the "new account" functions shared goes again
                st, body = fw.api("POST", "/auth/login", None, {"email": fw.sessions.fresh_email, "password": fw.FRESH_PASSWORD}, raw=True)
                if st == 200:
                    fw.forget(token=body["access_token"])
                print(f"clean-up: the new customer {fw.sessions.fresh_email} " + ("deleted" if st == 200 else f"NOT deleted (sign-in {st})"), flush=True)
                fw.sessions.states.pop(("web", "fresh"), None)
            json.dump({"|".join(k): v for k, v in fw.sessions.states.items()}, open(saved, "w", encoding="utf-8"))
        browser.close()
    json.dump(rows, open(f"{OUT}/functional-{PHASE}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    fails = sum(r["result"] == "FAIL" for r in rows)
    print(f"{len(rows) - fails}/{len(rows)} pass ({PHASE})")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
