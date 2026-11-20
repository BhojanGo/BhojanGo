"""The R21 load test's results, from one run's output directory (load-test.yml).

    python tools/load/rush_report.py <out dir>

Reads summary.json (k6 --summary-export, setup_data already dropped), console.log
(k6's console: the RT|... lines tools/load/rush.js writes) and samples.csv
(tools/load/sample.sh). Writes report.md (also printed, for the job summary),
realtime.json and verdict.txt ("pass" or "fail: ..."). Standard library only.

Lost realtime updates are counted, not guessed:
- tracking (customer's WebSocket): every rider fix that realtime published for an
  order (a ping whose answer names the order) while a tracking socket for that
  order was open, against the location_update messages that socket received (same
  fix timestamp). Likewise every status a kitchen or rider set, against the
  status_change messages. A socket only owes what was published after it said
  "connected" and early enough before it closed (2 s for locations, 10 s for
  statuses, which travel through the outbox and the event bus).
- kitchen tablets: every order that reached "placed", against each of its kitchen's
  tablets seeing it on the board.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TARGETS = [  # (label, trend, p95 limit ms)
    ("Home for an address (`GET /discover`)", "t_discover", 500),
    ("Menu (`GET /restaurants/{id}/menu`)", "t_menu", 500),
    ("Quote (`POST /pricing/quote`)", "t_quote", 500),
    ("Place order (`POST /orders`)", "t_place_order", 1500),
    ("Payment start (`POST /payments/initiate`)", "t_pay_initiate", 1500),
    ("Payment confirm (gateway event applied)", "t_pay_confirm", 1500),
    ("Order status (`GET /orders/{id}`)", "t_order_status", 500),
    ("Kitchen board (`GET /orders/restaurant/{id}`)", "t_board", 500),
    ("Kitchen today (`GET /restaurants/{id}/today`)", "t_today", 500),
    ("Rider location ping (realtime)", "t_rider_ping", 500),
    ("Rider state poll (`GET /riders/me`)", "t_rider_me", 500),
    ("Tracking WebSocket connect", "ws_connect_ms", 500),
    ("Offer accept (realtime)", "t_offer_accept", None),
    ("Kitchen status change (`PUT /orders/{id}/status`)", "t_kitchen_status", None),
    ("Rider status change (picked up, delivered)", "t_rider_status", None),
    ("Realtime: rider fix to tracking socket", "rt_location_ms", None),
    ("Realtime: status event to tracking socket", "rt_status_ms", None),
    ("Payment confirmed to order shows placed", "placed_visible_ms", None),
]
LOC_GRACE_MS, STATUS_GRACE_MS, KITCHEN_GRACE_MS = 2000, 10000, 10000
RT_LINE = re.compile(r"RT\|([^\"\s\\]+)")


def ms(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v / 1000:.2f} s" if v >= 1000 else f"{v:.0f} ms"


def pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def realtime(lines: list[str]) -> dict:
    pubs, puts = [], []
    opens, closes = {}, {}
    locs, sts = defaultdict(list), defaultdict(set)
    placed, tablets, tablet_end, kseen = [], {}, {}, {}
    offers = defaultdict(dict)
    last_t = 0
    for line in lines:
        m = RT_LINE.search(line)
        if not m:
            continue
        f = m.group(1).split("|")
        kind = f[0]
        try:
            if kind == "pub":
                pubs.append((f[1], f[2], int(f[3]), int(f[4])))
                last_t = max(last_t, int(f[4]))
            elif kind == "put":
                puts.append((f[1], f[2], int(f[3]), int(f[4])))
            elif kind == "open":
                opens[(f[1], f[2])] = int(f[3])
            elif kind == "close":
                closes[(f[1], f[2])] = int(f[3])
            elif kind == "loc":
                locs[(f[1], f[2])].append(f[3])
            elif kind == "st":
                sts[(f[1], f[2])].add(f[3])
            elif kind == "kplaced":
                placed.append((f[1], f[2], int(f[3])))
            elif kind == "tablet":
                tablets[f[1]] = (f[2], int(f[3]))
            elif kind == "tablet_end":
                tablet_end[f[1]] = int(f[3])
            elif kind == "kseen":
                kseen.setdefault((f[1], f[3]), int(f[4]))
            elif kind in ("offer_ws", "offer_poll"):
                offers[(f[1], f[2])].setdefault(kind, int(f[3]))
        except (IndexError, ValueError):
            continue

    by_order_pub = defaultdict(list)
    for o, ts, t0, t1 in pubs:
        by_order_pub[o].append((ts, t0, t1))
    by_order_put = defaultdict(list)
    for o, st, t0, t1 in puts:
        by_order_put[o].append((st, t0, t1))

    loc_expected = loc_received = loc_dupes = 0
    st_expected = st_received = 0
    lost_loc, lost_st = [], []
    lost_by_status: dict[str, int] = defaultdict(int)
    unclosed = 0
    for (order, sess), t_open in opens.items():
        t_close = closes.get((order, sess))
        if t_close is None:
            unclosed += 1
            continue  # cut off by the end of the test: no window to judge
        got = locs.get((order, sess), [])
        got_set = set(got)
        loc_dupes += len(got) - len(got_set)
        for ts, t0, t1 in by_order_pub.get(order, []):
            if t0 >= t_open and t1 <= t_close - LOC_GRACE_MS:
                loc_expected += 1
                if ts in got_set:
                    loc_received += 1
                else:
                    lost_loc.append({"order": order, "session": sess, "fix": ts})
        for st, t0, t1 in by_order_put.get(order, []):
            if t0 >= t_open and t1 <= t_close - STATUS_GRACE_MS:
                st_expected += 1
                if st in sts.get((order, sess), set()):
                    st_received += 1
                else:
                    lost_st.append({"order": order, "session": sess, "status": st})
                    lost_by_status[st] += 1

    k_expected = k_seen = 0
    k_lat: list[float] = []
    lost_k = []
    for kitchen, order, t in placed:
        for tab, (k, start) in tablets.items():
            if k != kitchen or start > t or tablet_end.get(tab, 0) < t + KITCHEN_GRACE_MS:
                continue
            k_expected += 1
            seen = kseen.get((tab, order))
            if seen is None:
                lost_k.append({"tablet": tab, "kitchen": kitchen, "order": order})
            else:
                k_seen += 1
                k_lat.append(max(0, seen - t))

    ws_first = sum(1 for v in offers.values() if "offer_ws" in v and ("offer_poll" not in v or v["offer_ws"] <= v["offer_poll"]))
    poll_first = sum(1 for v in offers.values() if "offer_poll" in v and ("offer_ws" not in v or v["offer_poll"] < v["offer_ws"]))
    return {
        "tracking_sessions": len(opens), "sessions_cut_by_test_end": unclosed,
        "orders_tracked": len({o for o, _ in opens}),
        "location": {"published": len(pubs), "expected_on_open_sockets": loc_expected, "received": loc_received,
                     "lost": loc_expected - loc_received, "duplicates": loc_dupes, "lost_examples": lost_loc[:20]},
        "status": {"set": len(puts), "expected_on_open_sockets": st_expected, "received": st_received,
                   "lost": st_expected - st_received, "lost_by_status": dict(lost_by_status), "lost_examples": lost_st[:20]},
        "kitchen": {"orders_placed": len(placed), "tablets": len(tablets), "expected_tablet_sightings": k_expected,
                    "seen": k_seen, "lost": k_expected - k_seen,
                    "placed_to_seen_ms": {"p50": pct(k_lat, 50), "p95": pct(k_lat, 95), "p99": pct(k_lat, 99), "max": max(k_lat) if k_lat else None},
                    "lost_examples": lost_k[:20]},
        "offers": {"offers_seen": len(offers), "first_on_ws": ws_first, "first_on_poll": poll_first},
    }


def samples(path: Path) -> dict:
    vals: dict[str, list[float]] = defaultdict(list)
    if path.exists():
        with path.open() as f:
            for row in csv.DictReader(f):
                try:
                    vals[row["metric"]].append(float(row["value"]))
                except (TypeError, ValueError):
                    continue
    return {k: {"avg": sum(v) / len(v), "max": max(v), "n": len(v)} for k, v in vals.items() if v}


def profile(path: Path) -> dict | None:
    """py-spy's raw output (collapsed stacks: "frame;frame;... count") -> the frames that cost most."""
    if not path.exists():
        return None
    ours: dict[str, int] = defaultdict(int)
    leaf: dict[str, int] = defaultdict(int)
    total = 0
    for line in path.read_text(errors="replace").splitlines():
        stack, _, n = line.rpartition(" ")
        if not stack or not n.isdigit():
            continue
        count = int(n)
        frames = [re.sub(r" \((?:/srv/)?(.*?):\d+\)$", r" ()", f) for f in stack.split(";")]
        if any(f.startswith(("process ", "thread ")) and "idle" in f for f in frames):
            continue
        total += count
        for f in dict.fromkeys(f for f in frames if "core_api/" in f or "shared/" in f):
            ours[f] += count
        leaf[frames[-1]] += count
    if not total:
        return None
    top = lambda d: sorted(d.items(), key=lambda kv: -kv[1])[:20]  # noqa: E731
    return {"samples": total, "ours": top(ours), "leaf": top(leaf)}


def main() -> int:
    out = Path(sys.argv[1])
    summary = json.loads((out / "summary.json").read_text()) if (out / "summary.json").exists() else {"metrics": {}}
    met = summary.get("metrics", {})
    log = (out / "console.log").read_text(errors="replace").splitlines() if (out / "console.log").exists() else []
    rtm = realtime(log)
    smp = samples(out / "samples.csv")
    (out / "realtime.json").write_text(json.dumps(rtm, indent=1))

    fails: list[str] = []
    md = ["## Requests (k6)", "", "| Request | n | p50 | p95 | p99 | max | Target (p95) | |", "|---|---|---|---|---|---|---|---|"]
    for label, key, limit in TARGETS:
        m = met.get(key)
        if not m:
            md.append(f"| {label} | 0 | - | - | - | - | {ms(limit) if limit else '-'} | no data |")
            if limit:
                fails.append(f"{key}: no data")
            continue
        p95 = m.get("p(95)")
        verdict = ""
        if limit:
            ok = p95 is not None and p95 < limit
            verdict = "pass" if ok else "**fail**"
            if not ok:
                fails.append(f"{key} p95 {ms(p95)}")
        md.append(f"| {label} | {int(m.get('count', 0))} | {ms(m.get('p(50)'))} | {ms(p95)} | {ms(m.get('p(99)'))} | {ms(m.get('max'))} | "
                  f"{ms(limit) if limit else '-'} | {verdict} |")

    reqs = met.get("http_reqs", {}).get("count", 0)
    failed = met.get("http_req_failed", {})
    n_failed = failed.get("passes", 0)
    errs = met.get("errors", {}).get("count", 0)
    wse = met.get("ws_errors", {}).get("count", 0)
    err_lines = [line for line in log if "ERR|" in line]
    by_step: dict[str, int] = defaultdict(int)
    for line in err_lines:
        m = re.search(r"ERR\|([^|]+)\|(\d+)", line)
        if m:
            by_step[f"{m.group(1)} {m.group(2)}"] += 1
    md += ["", "## Errors", "",
           f"- HTTP requests: {int(reqs):,}; failed (4xx/5xx): {int(n_failed):,} ({100 * failed.get('value', 0):.2f}%)",
           f"- Unexpected answers by step: {int(errs)}" + (f" ({', '.join(f'{k}: {v}' for k, v in sorted(by_step.items()))})" if by_step else ""),
           f"- WebSocket errors: {int(wse)}",
           f"- Orders placed: {int(met.get('orders_placed', {}).get('count', 0))}, delivered (seen by the customer): "
           f"{int(met.get('orders_delivered', {}).get('count', 0))}"]
    if failed.get("value", 0) >= 0.01:
        fails.append(f"http_req_failed {100 * failed.get('value', 0):.2f}%")

    loc, st, k = rtm["location"], rtm["status"], rtm["kitchen"]
    kl = k["placed_to_seen_ms"]
    md += ["", "## Realtime: published vs received", "",
           "| Updates | Published | Owed to open sockets | Received | Lost |", "|---|---|---|---|---|",
           f"| Rider location to tracking sockets | {loc['published']:,} | {loc['expected_on_open_sockets']:,} | {loc['received']:,} | **{loc['lost']}** |",
           f"| Order status to tracking sockets | {st['set']:,} | {st['expected_on_open_sockets']:,} | {st['received']:,} | **{st['lost']}** |",
           f"| New orders on kitchen tablets (each tablet) | {k['orders_placed']:,} orders | {k['expected_tablet_sightings']:,} | {k['seen']:,} | **{k['lost']}** |",
           "",
           f"Tracking sessions: {rtm['tracking_sessions']} on {rtm['orders_tracked']} orders ({rtm['sessions_cut_by_test_end']} cut off by the end of the test, not judged). "
           f"Duplicate location messages: {loc['duplicates']}. Lost statuses by status: {st['lost_by_status'] or 'none'}. "
           f"Placed to seen on a tablet: p50 {ms(kl['p50'])}, p95 {ms(kl['p95'])}, p99 {ms(kl['p99'])}, max {ms(kl['max'])}. "
           f"Offers: {rtm['offers']['offers_seen']}, first over /ws/rider {rtm['offers']['first_on_ws']}, first by the 5 s poll {rtm['offers']['first_on_poll']}."]
    lost = loc["lost"] + st["lost"] + k["lost"]
    if lost:
        fails.append(f"{lost} realtime updates lost")
    if not loc["expected_on_open_sockets"]:
        fails.append("no location updates were owed to a tracking socket (nothing measured)")

    md += ["", "## Database, CPU and memory (every 5 s)", "", "| Measure | Average | Peak |", "|---|---|---|"]
    order = ["pg_connections", "pg_active", "pg_max_connections", "redis_clients", "tcp_realtime", "tcp_core_api", "host_cpu_busy_pct", "host_mem_used_mib"]
    keys = order + sorted(k for k in smp if k.startswith("cpu_pct.")) + sorted(k for k in smp if k.startswith("mem_mib.")) + ["redis_used_mib"]
    for key in keys:
        if key in smp:
            s = smp[key]
            md.append(f"| {key} | {s['avg']:.1f} | {s['max']:.1f} |")

    prof = profile(out / "profile-core-api.txt")
    if prof:
        md += ["", "## Where core-api spent its CPU (py-spy, 1 minute mid-window)", "",
               f"{prof['samples']:,} samples. Inclusive share of our own code's frames (top 20), then the hottest leaf frames.", "",
               "| Frame (ours) | Share |", "|---|---|"]
        md += [f"| `{f}` | {100 * n / prof['samples']:.1f}% |" for f, n in prof["ours"]]
        md += ["", "| Leaf frame | Share |", "|---|---|"]
        md += [f"| `{f}` | {100 * n / prof['samples']:.1f}% |" for f, n in prof["leaf"]]

    verdict = "pass" if not fails else "fail: " + "; ".join(fails)
    md = [f"# Load test: Boise rush at 3x launch - {verdict.split(':')[0].upper()}", "", f"Verdict: {verdict}", ""] + md
    (out / "report.md").write_text("\n".join(md) + "\n")
    (out / "verdict.txt").write_text(verdict + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
