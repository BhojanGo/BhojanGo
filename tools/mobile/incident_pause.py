"""Pause or resume ordering in Hyderabad and Spice Route Kitchen on THIS machine's stack (R18), so the
customer app's flow apps/customer/.maestro/stack/04-incident-pause.yaml can screenshot the paused-city strip,
"Closed for now" and the bag. Runs on the host (tools/mobile/stack-screens.sh), as the seed's Hyderabad
city ops through admin's incident API. Never against QA or production (tools/target_guard.py).
    python tools/mobile/incident_pause.py on|off [core url, default http://localhost:8001]
"""
import os
import sys

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from target_guard import ensure_safe_api  # noqa: E402
from totp_signin import finish  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else ""
CORE = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8001").rstrip("/") + "/api/v1"
ensure_safe_api(CORE)
if MODE not in ("on", "off"):
    sys.exit("usage: incident_pause.py on|off [core url]")

with httpx.Client(timeout=30) as c:
    body = c.post(f"{CORE}/auth/login", json={"email": "ops.hyd@example.com", "password": "BhojanGoAdmin1"}).json()
    tokens = finish(lambda path, data: c.post(f"{CORE}{path}", json=data).json(), "ops.hyd@example.com", body)
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    kitchen = next(r["id"] for r in c.get(f"{CORE}/restaurants", params={"limit": 50}).json()["items"]
                   if r["name"] == "Spice Route Kitchen")
    why = {"reason": "Stack screenshots: incident drill", "confirm": True}
    if MODE == "on":
        r = c.post(f"{CORE}/incidents/ordering-pauses", headers=h, json={**why, "scope": "IN-TG-HYD", "note": "Back by 9 pm"})
        print("ordering paused:", r.status_code)
        r = c.post(f"{CORE}/incidents/kitchens/{kitchen}/pause", headers=h, json=why)
        print("kitchen paused:", r.status_code)
    else:
        for p in c.get(f"{CORE}/incidents/ordering-pauses/active").json():
            if p["scope"] == "IN-TG-HYD":
                print("ordering resumed:", c.post(f"{CORE}/incidents/ordering-pauses/{p['id']}/end", headers=h, json=why).status_code)
        print("kitchen resumed:", c.post(f"{CORE}/incidents/kitchens/{kitchen}/resume", headers=h, json=why).status_code)
