"""Open (or restore) Hyderabad and its restaurants around the clock for app E2E runs (tools/mobile/e2e.sh).
python hours.py open | close"""
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

API = "http://localhost:8001/api/v1"
c = httpx.Client(timeout=30)


def login(email, pw):
    for _ in range(30):
        r = c.post(f"{API}/auth/login", json={"email": email, "password": pw})
        if r.status_code != 429:
            return {"Authorization": f"Bearer {r.json()['access_token']}"}
        time.sleep(5)


cm, partner = login("cm.in@example.com", "BhojanGoAdmin1"), login("partner.hyd@example.com", "BhojanGo123")
today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
ids = [r["id"] for r in c.get(f"{API}/restaurants", params={"limit": 50}).json()["items"] if r["city"] == "Hyderabad"]
if sys.argv[1] == "open":
    c.patch(f"{API}/markets/cities/IN-TG-HYD", headers=cm, json={"service_hours": {"open": "00:00", "close": "00:00"}})
    for d in (today, today + timedelta(days=1)):
        for rid in ids:
            c.put(f"{API}/restaurants/{rid}/hours/overrides/{d}", headers=partner, json={"closed": False, "opens": "00:00", "closes": "00:00", "note": "E2E"})
else:
    for d in (today, today + timedelta(days=1)):
        for rid in ids:
            c.delete(f"{API}/restaurants/{rid}/hours/overrides/{d}", headers=partner)
    c.patch(f"{API}/markets/cities/IN-TG-HYD", headers=cm, json={"service_hours": {"open": "07:00", "close": "23:30"}})
print(sys.argv[1], len(ids), "restaurants")
