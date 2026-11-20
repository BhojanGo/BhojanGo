"""R22: where core_api's CPU goes, path by path (.github/workflows/load-test.yml, after the rush).

    python tools/load/paths.py <out dir>

The rush's py-spy minute (profile.sh) mixes every request type, and the handler frames
alone can't say which request a middleware or routing sample belonged to. So, on the
same throwaway stack once the rush is over, this sends one request type at a time,
one request after another, while py-spy records every core-api process. Each profile
then holds one path only (middleware, routing and serialization included), and
tools/load/profile_report.py turns it into CPU milliseconds per request, by hot path.

Paths: home for an address (two passes over 200 addresses, so half are per-address
cache hits, as in the rush), menu, quote, place order (quoted beforehand, not
profiled), payment confirm (the fake gateway's signed event; started beforehand),
order status and the kitchen board. Each is timed as well (wall ms, one at a time).

Never QA or production: the API must be on this machine (the workflow has also run
tools/target_guard.py). Writes path-<name>.txt (py-spy raw), path-<name>.log and
paths.json. No tokens are written anywhere.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

API = os.environ.get("API", "http://localhost:8001/api/v1")
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "bhojango")
SIDE = "load-pyspy"
RATE = 200  # samples a second
PASSWORD = "BhojanGo123"
ZONES = [(43.580, -116.250, 43.605, -116.215), (43.598, -116.290, 43.620, -116.250), (43.590, -116.215, 43.605, -116.185),
         (43.600, -116.185, 43.625, -116.150), (43.555, -116.215, 43.590, -116.160)]
COUNTS = {"discover": 2000, "menu": 2000, "quote": 600, "place_order": 200, "pay_confirm": 200, "order_status": 1500,
          "board": 1000}

if urlparse(API).hostname not in ("localhost", "127.0.0.1"):
    sys.exit(f"REFUSED: {API} is not this machine (load tests run on a throwaway stack only)")

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
client = httpx.Client(timeout=60)
_ip = 0


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=300)


def login(email: str) -> str:
    global _ip
    _ip += 1
    r = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD},
                    headers={"X-Real-IP": f"10.200.{_ip >> 8 & 255}.{_ip & 255}"})
    r.raise_for_status()
    return r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── py-spy, in a side container sharing core-api's process namespace ─────────
def spy_setup() -> None:
    run("docker", "rm", "-f", SIDE, check=False)
    run("docker", "run", "-d", "--name", SIDE, "--pid", f"container:{PROJECT}-core-api-1", "--cap-add", "SYS_PTRACE",
        "-v", f"{OUT.resolve()}:/out", "python:3.12-slim", "sleep", "3000")
    run("docker", "exec", SIDE, "pip", "install", "-q", "py-spy==0.4.0")


def spy_start(name: str) -> None:
    # exec, so the recorded pid is py-spy itself (a backgrounded child would ignore SIGINT).
    run("docker", "exec", "-d", SIDE, "sh", "-c",
        f"echo $$ > /tmp/spy.pid; exec py-spy record --subprocesses --pid 1 --rate {RATE} --duration 280 "
        f"--format raw --nonblocking --output /out/path-{name}.txt > /out/path-{name}.log 2>&1")
    time.sleep(3)  # attached


def spy_stop(name: str) -> None:
    run("docker", "exec", SIDE, "sh", "-c", "kill -INT $(cat /tmp/spy.pid)", check=False)
    for _ in range(60):  # py-spy writes the file when it stops
        if (OUT / f"path-{name}.txt").exists() and "Wrote" in (OUT / f"path-{name}.log").read_text(errors="replace"):
            return
        time.sleep(1)


def phase(name: str, step) -> None:  # type: ignore[no-untyped-def]
    """Profile `step` (one request per call, returns its response) COUNTS[name] times."""
    times: list[float] = []
    bad: dict[str, int] = {}
    if not COUNTS[name]:
        print(name, "skipped: nothing to send", flush=True)
        return
    spy_start(name)
    t0 = time.perf_counter()
    for i in range(COUNTS[name]):
        s = time.perf_counter()
        r = step(i)
        times.append((time.perf_counter() - s) * 1000)
        if r.status_code >= 400:
            bad[str(r.status_code)] = bad.get(str(r.status_code), 0) + 1
    wall = time.perf_counter() - t0
    spy_stop(name)
    times.sort()
    results[name] = {
        "n": len(times), "errors": bad, "wall_s": round(wall, 2), "rate": RATE,
        "mean_ms": round(sum(times) / len(times), 1), "p50_ms": round(times[len(times) // 2], 1),
        "p95_ms": round(times[int(len(times) * 0.95) - 1], 1),
    }
    print(name, json.dumps(results[name]), flush=True)


results: dict[str, dict] = {}


def main() -> None:
    random.seed(22)
    # The kitchens and what they sell (as rush.js does).
    partner = login("partner.boi@example.com")
    mine = {k["id"] for k in client.get(f"{API}/restaurants/mine", headers=auth(partner)).json()}
    listed = [k for k in client.get(f"{API}/restaurants", params={"limit": 100}).json()["items"] if k["city"] == "Boise"]
    kitchens: dict[str, list[str]] = {}
    for k in listed:
        menu = client.get(f"{API}/restaurants/{k['id']}/menu").json()
        items = [i["id"] for c in menu.get("categories") or [] for i in c.get("items") or []
                 if i["is_available"] and not i["sold_out_today"]
                 and not any((g.get("min_picks") or 0) > 0 for g in i.get("option_groups") or [])]
        if items:
            kitchens[k["id"]] = items
    customers = []
    for n in range(1, 61):
        tok = login(f"customer{n}.boi@example.com")
        home = (client.get(f"{API}/me/addresses", headers=auth(tok)).json() or [None])[0]
        if not home:
            continue
        near = client.get(f"{API}/discover", params={"lat": home["lat"], "lng": home["lng"]}).json()["restaurants"]
        ks = [r["id"] for r in near if r.get("open_now") and r["id"] in kitchens]
        if ks:
            customers.append({"token": tok, "address": home["id"], "zip": home.get("postal_code") or "83702",
                              "street": home.get("street") or "1 Main St", "kitchens": ks})
    if not customers:
        sys.exit("no customers with an open kitchen nearby")
    print(f"paths: {len(kitchens)} kitchens, {len(customers)} customers", flush=True)

    def cart(kid: str) -> list[dict]:
        picks = random.sample(kitchens[kid], min(3, len(kitchens[kid])))
        return [{"menu_item_id": i, "quantity": 2} for i in picks]

    def quote(c: dict, kid: str, items: list[dict]) -> httpx.Response:
        return client.post(f"{API}/pricing/quote", headers=auth(c["token"]),
                           json={"restaurant_id": kid, "items": items, "deliver_to": {"address_id": c["address"]}})

    addresses = []
    for vu in range(1, 201):
        z = ZONES[vu % len(ZONES)]
        f, g = (vu * 7919 % 1000) / 1000, (vu * 104729 % 1000) / 1000
        addresses.append((round(z[0] + f * (z[2] - z[0]), 4), round(z[1] + g * (z[3] - z[1]), 4)))
    kids = list(kitchens)

    spy_setup()
    phase("discover", lambda i: client.get(f"{API}/discover",
                                           params={"lat": addresses[i % 200][0], "lng": addresses[i % 200][1]}))
    phase("menu", lambda i: client.get(f"{API}/restaurants/{kids[i % len(kids)]}/menu"))

    def one_quote(i: int) -> httpx.Response:
        c = customers[i % len(customers)]
        kid = random.choice(c["kitchens"])
        return quote(c, kid, cart(kid))
    phase("quote", one_quote)

    # Place order: quoted beforehand (not profiled).
    ready = []
    for i in range(COUNTS["place_order"]):
        c = customers[i % len(customers)]
        kid = random.choice(c["kitchens"])
        items = cart(kid)
        q = quote(c, kid, items)
        if q.status_code == 200:
            ready.append((c, kid, items, q.json()["token"]))
    COUNTS["place_order"] = len(ready)
    placed: list[tuple[dict, str]] = []

    def place(i: int) -> httpx.Response:
        c, kid, items, token = ready[i]
        r = client.post(f"{API}/orders", headers={**auth(c["token"]), "X-Idempotency-Key": str(uuid.uuid4())},
                        json={"restaurant_id": kid, "items": items, "payment_method": "card", "quote_token": token,
                              "delivery_address": {"street": c["street"], "city": "Boise", "state": "ID",
                                                   "zip": c["zip"], "country": "US"}})
        if r.status_code == 201:
            placed.append((c, r.json()["id"]))
        return r
    phase("place_order", place)

    # Payment confirm: started beforehand (not profiled).
    intents = []
    for c, oid in placed:
        p = client.post(f"{API}/payments/initiate", headers=auth(c["token"]),
                        json={"order_id": oid, "payment_method_type": "card"})
        if p.status_code == 201:
            intents.append((c, p.json()["payment_intent_id"], oid))
    COUNTS["pay_confirm"] = len(intents)
    phase("pay_confirm", lambda i: client.post(f"{API}/payments/fake/{intents[i][1]}/complete",
                                               headers=auth(intents[i][0]["token"]), json={"outcome": "succeeded"}))
    phase("order_status", lambda i: client.get(f"{API}/orders/{placed[i % len(placed)][1]}",
                                               headers=auth(placed[i % len(placed)][0]["token"])))
    boards = [k for k in kids if k in mine] or kids
    phase("board", lambda i: client.get(f"{API}/orders/restaurant/{boards[i % len(boards)]}", params={"limit": 100},
                                        headers=auth(partner)))
    (OUT / "paths.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    try:
        main()
    finally:
        run("docker", "rm", "-f", SIDE, check=False)
