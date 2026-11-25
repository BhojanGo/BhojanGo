"""R40 item 4: one Boise order traced through every finance screen, against the LOCAL stack only.

    cd backend && uv run python ../tools/finance/worked_example.py

Boise Bowl Co. sells three dishes at 3.99, 10.99 and 22.00 (added to its menu here if missing); a customer 3 miles away
orders one of each, tips $3 and pays by card (the local fake card). The order is then delivered in a week of its own
(long ago, so the screens hold only it), a payout run is prepared for that week, and every number is read back from
the APIs behind the screens: the bill, the restaurant's statement line, the delivery partner's line, Reconciliation
and Contribution. Prints a table and writes worked_example.json (next to this file's caller) for the report.
Refuses anything but localhost (tools/target_guard.py)."""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE)]
from totp_signin import finish  # noqa: E402

CORE = os.environ.get("CORE", "http://localhost:8001") + "/api/v1"
assert CORE.startswith("http://localhost"), "the worked example runs against the local stack only"
PG = os.environ.get("PG_CONTAINER", "r40-postgres-1")
DISHES = (("R40 Garlic Knots", "3.99"), ("R40 Kale Caesar", "10.99"), ("R40 Paella Bowl", "22.00"))


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict | list:
    req = urllib.request.Request(f"{CORE}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {}),
                                          **({"X-Idempotency-Key": str(uuid.uuid4())} if path == "/orders" else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path}: {e.code} {e.read()[:400]!r}") from e
    return json.loads(raw) if raw else {}


def login(email: str, password: str = "BhojanGo123") -> str:
    body = api("POST", "/auth/login", None, {"email": email, "password": password})
    return finish(lambda p, d: api("POST", p, None, d), email, body)["access_token"]  # type: ignore[arg-type]


def sql(q: str) -> str:
    return subprocess.run(["docker", "exec", PG, "psql", "-U", "bhojango", "-d", "bhojango", "-qAt", "-c", q],
                          capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    owner, cust = login("partner.boi@example.com"), login("customer1.boi@example.com")
    finance = login("finance.us@example.com", "BhojanGoAdmin1")
    rest = next(r for r in api("GET", "/restaurants?limit=100")["items"] if r["name"] == "Boise Bowl Co.")  # type: ignore[index]
    rid = rest["id"]
    menu = {i["name"]: i for c in api("GET", f"/restaurants/{rid}/menu")["categories"] for i in c["items"]}  # type: ignore[index]
    for name, price in DISHES:
        if name not in menu:
            api("POST", f"/restaurants/{rid}/menu-items", owner, {"name": name, "price": price, "category": "Worked example",
                                                                    "description": f"{name}, R40 worked example."})
    ids = dict(line.split("|") for line in sql(  # the public menu is cached for a while: read the new dishes' ids directly
        f"SELECT name, id FROM menu_items WHERE restaurant_id = '{rid}' AND name LIKE 'R40 %'").splitlines())
    cart = [{"menu_item_id": ids[n], "quantity": 1} for n, _ in DISHES]
    lat, lng = (float(v) for v in sql(f"SELECT lat, lng FROM restaurants WHERE id = '{rid}'").split("|"))
    q, to = None, None
    for deg in range(0, 360, 15):  # 3 miles away, in the first direction that is inside a delivery zone
        d = 3 * 1.609344
        to = {"lat": lat + d / 111.0 * math.cos(math.radians(deg)),
              "lng": lng + d / (111.0 * math.cos(math.radians(lat))) * math.sin(math.radians(deg))}
        try:
            q = api("POST", "/pricing/quote", cust, {"restaurant_id": rid, "items": cart, "deliver_to": to, "tip": "3"})
            break
        except SystemExit:
            continue
    assert q is not None and to is not None, "no point 3 miles away is in a delivery zone"
    order = api("POST", "/orders", cust, {"restaurant_id": rid, "items": cart, "payment_method": "card", "quote_token": q["token"],  # type: ignore[index]
                                          "delivery_address": {"street": "1 Worked Example Way", "city": "Boise", "state": "ID",
                                                               "zip": "83702", "country": "US", "lat": to["lat"], "lng": to["lng"]}})
    oid = order["id"]  # type: ignore[index]
    init = api("POST", "/payments/initiate", cust, {"order_id": oid, "payment_method_type": "card"})
    api("POST", f"/payments/fake/{init['payment_intent_id']}/complete", cust, {"outcome": "succeeded"})  # type: ignore[index]
    start = date(2003, 1, 6) + timedelta(weeks=random.randint(0, 600))
    at = datetime.combine(start + timedelta(days=2), time(19), tzinfo=ZoneInfo("America/Boise")).isoformat()
    sql(f"UPDATE orders SET status = 'delivered', actual_delivery_time = '{at}', created_at = TIMESTAMPTZ '{at}' - interval '40 minutes', "
        f"rider_assigned_at = TIMESTAMPTZ '{at}' - interval '30 minutes', picked_up_at = TIMESTAMPTZ '{at}' - interval '15 minutes', "
        f"driver_id = (SELECT id FROM users WHERE email = 'rider1.boi@example.com') WHERE id = '{oid}'")
    end = start + timedelta(days=7)
    run = api("POST", "/finance/payout-runs", finance, {"country": "US", "period_start": str(start), "period_end": str(end)})
    detail = api("GET", f"/finance/payout-runs/{run['id']}", finance)  # type: ignore[index]
    rest_st = next(s for s in detail["statements"] if s["payee_type"] == "restaurant")  # type: ignore[index]
    rider_st = next(s for s in detail["statements"] if s["payee_type"] == "rider")  # type: ignore[index]
    rline = next(ln for ln in api("GET", f"/finance/statements/{rest_st['id']}", finance)["lines"] if ln["order_id"] == oid)  # type: ignore[index]
    pline = next(ln for ln in api("GET", f"/finance/statements/{rider_st['id']}", finance)["lines"] if ln["order_id"] == oid)  # type: ignore[index]
    rec = api("GET", f"/finance/reconciliation?country=US&start={start}&end={end}", finance)["money"]  # type: ignore[index]
    con = api("GET", f"/finance/contribution?scope=US&start={start}&end={end}", finance)["all"]["totals"]  # type: ignore[index]
    snap = json.loads(sql(f"SELECT json_build_object('lines', lines, 'split', split, 'context', context) FROM order_pricing_snapshots "
                          f"WHERE order_id = '{oid}'"))
    card_fee = sql(f"SELECT card_fee FROM orders WHERE id = '{oid}'")
    miles = Decimal(str(snap["context"].get("distance", 0)))
    out = {"order_id": oid, "week": [str(start), str(end)], "run_id": run["id"],  # type: ignore[index]
           "restaurant_statement_id": rest_st["id"], "rider_statement_id": rider_st["id"], "distance": str(miles),
           "bill": [(ln["label"], ln["amount"]) for ln in snap["lines"]], "total": q["total"],  # type: ignore[index]
           "card_fee": card_fee, "restaurant_line": rline, "rider_line": pline,
           "reconciliation": rec, "contribution": con}
    print(json.dumps(out, indent=2, default=str))
    with open(os.environ.get("OUT", "worked_example.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    m = lambda v: f"${Decimal(str(v)):.2f}"  # noqa: E731
    print("\nCustomer pays", m(q["total"]), "| restaurant receives", m(rline["net"]), "(card fee", m(card_fee) + ")",  # type: ignore[index]
          "| partner", m(pline["total"]), "| tax", m(Decimal(rec["tax_owed"]) / 100), "| BhojanGo keeps", m(Decimal(rec["platform_revenue"]) / 100))
    assert not math.isnan(float(miles))


if __name__ == "__main__":
    main()
