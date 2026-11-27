"""Open (or restore) Hyderabad and Boise and their restaurants around the clock
for E2E runs (tools/mobile/e2e.sh, tools/web/e2e.sh, tools/admin/e2e.sh).
python hours.py open | close"""
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

API = "http://localhost:8001/api/v1"

# Tests never write to QA or production (tools/target_guard.py).
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from target_guard import ensure_safe_api  # noqa: E402

ensure_safe_api(API)
c = httpx.Client(timeout=30)

# city code, city name, timezone, country manager, partner, usual service hours (seed)
CITIES = [
    ("IN-TG-HYD", "Hyderabad", "Asia/Kolkata", "cm.in@example.com", "partner.hyd@example.com", {"open": "07:00", "close": "23:30"}),
    ("US-ID-BOI", "Boise", "America/Boise", "cm.us@example.com", "partner.boi@example.com", {"open": "08:00", "close": "23:00"}),
]


def zone(tz):
    """The city's zone; fixed offsets where the host has no tz database (Windows Python
    without tzdata). Today and tomorrow are both opened, so an hour of DST can't matter."""
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours={"Asia/Kolkata": 5.5, "America/Boise": -7}[tz]))


def login(email, pw):
    for _ in range(30):
        r = c.post(f"{API}/auth/login", json={"email": email, "password": pw})
        if r.status_code != 429:
            from totp_signin import finish  # admins: the second step (seed key)

            body = finish(lambda path, data: c.post(f"{API}{path}", json=data).json(), email, r.json())
            return {"Authorization": f"Bearer {body['access_token']}"}
        time.sleep(5)


listed = c.get(f"{API}/restaurants", params={"limit": 100}).json()["items"]
for code, name, tz, cm_email, partner_email, usual in CITIES:
    cm = login(cm_email, "BhojanGoAdmin1")
    today = datetime.now(zone(tz)).date()  # each city's own day
    ids = [r["id"] for r in listed if r["city"] == name]
    if sys.argv[1] == "open":
        c.patch(f"{API}/markets/cities/{code}", headers=cm, json={"service_hours": {"open": "00:00", "close": "00:00"}})
        for d in (today, today + timedelta(days=1)):
            for rid in ids:
                # R45: the country manager's token, so every restaurant opens (the partner's opened only its own:
                # at Hyderabad night the demo customer's past restaurants stayed closed and the demo order stopped)
                c.put(f"{API}/restaurants/{rid}/hours/overrides/{d}", headers=cm,
                      json={"closed": False, "opens": "00:00", "closes": "00:00", "note": "E2E"})
    else:
        for d in (today, today + timedelta(days=1)):
            for rid in ids:
                c.delete(f"{API}/restaurants/{rid}/hours/overrides/{d}", headers=cm)
        c.patch(f"{API}/markets/cities/{code}", headers=cm, json={"service_hours": usual})
    print(sys.argv[1], name, len(ids), "restaurants")
