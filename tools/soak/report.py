"""Summarise a soak run directory (tools/soak/run.sh writes it):
completion, delivery times, resource growth, alerts, log errors.

    python tools/soak/report.py tools/soak/out/<run>
Writes <run>/report.json and prints the same as Markdown.
"""
import csv
import json
import re
import statistics
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

PROMETHEUS = "http://localhost:9090"
# What counts as growth: the last 20 minutes against minutes 10-30 (after the
# stack has warmed up), for the series that would leak.
WATCH = ("mem_mib.core-api", "mem_mib.realtime", "mem_mib.worker", "mem_mib.web", "mem_mib.admin", "mem_mib.postgres",
         "mem_mib.redis", "pg_connections", "redis_clients", "redis_used_mib", "redis_keys", "tcp_realtime", "tcp_core_api")


def load_samples(path: Path) -> dict[str, list[tuple[str, float]]]:
    series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    if not path.exists():
        return series
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                series[row["metric"]].append((row["time"], float(row["value"])))
            except (ValueError, TypeError):
                continue
    return series


def growth(points: list[tuple[str, float]]) -> dict:
    vals = [v for _, v in points]
    if len(vals) < 40:
        return {"samples": len(vals), "max": max(vals) if vals else None}
    warm, last = vals[10:30], vals[-20:]
    a, b = statistics.mean(warm), statistics.mean(last)
    return {"samples": len(vals), "warm_avg": round(a, 1), "last_avg": round(b, 1), "max": round(max(vals), 1),
            "change_pct": round((b - a) / a * 100, 1) if a else None}


def prometheus_alerts(start: str, end: str) -> list[dict]:
    """Every alert that was firing at any minute of the window (Prometheus's ALERTS series)."""
    q = urllib.parse.urlencode({"query": 'ALERTS{alertstate="firing"}', "start": start, "end": end, "step": "60"})
    try:
        with urllib.request.urlopen(f"{PROMETHEUS}/api/v1/query_range?{q}", timeout=20) as r:
            data = json.load(r)["data"]["result"]
    except Exception as e:  # noqa: BLE001
        return [{"error": f"prometheus: {e}"}]
    out = []
    for s in data:
        m = s["metric"]
        out.append({"alert": m.get("alertname"), "city": m.get("city"), "severity": m.get("severity"),
                    "firing_minutes": len(s["values"])})
    return out


def error_kinds(lines: list[str]) -> list[tuple[str, int]]:
    kinds: Counter = Counter()
    for ln in lines:
        svc = ln.split("]", 1)[0].strip("[")
        m = re.search(r'"event": ?"([^"]+)"', ln)
        key = m.group(1) if m else re.sub(r"[0-9a-f-]{8,}|\d+", "#", ln.split("|", 1)[-1].strip())[:90]
        kinds[f"{svc}: {key}"] += 1
    return kinds.most_common(25)


def main(run_dir: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    d = Path(run_dir)
    res = json.loads((d / "soak-result.json").read_text()) if (d / "soak-result.json").exists() else {"summary": {}}
    s = res["summary"]
    start = (d / "started_at").read_text().strip()
    end = (d / "ended_at").read_text().strip() if (d / "ended_at").exists() else start
    series = load_samples(d / "samples.csv")
    errors = (d / "log-errors.txt").read_text(errors="replace").splitlines() if (d / "log-errors.txt").exists() else []
    try:
        stored = json.loads((d / "alerts.json").read_text() or "[]")
    except ValueError:
        stored = []
    report = {
        "window": [start, end], "summary": s,
        "growth": {k: growth(series[k]) for k in WATCH if k in series},
        "alerts_prometheus": prometheus_alerts(start, end),
        "alerts_admin_console": [{"name": a.get("name"), "city": a.get("city"), "status": a.get("status"),
                                  "starts_at": a.get("starts_at"), "ends_at": a.get("ends_at")} for a in stored],
        "log_errors": {"lines": len(errors), "kinds": error_kinds(errors)},
        "rider_waits": json.loads((d / "rider-waits.json").read_text() or "{}") if (d / "rider-waits.json").exists() else {},
    }
    (d / "report.json").write_text(json.dumps(report, indent=1))

    print(f"# Soak {start} → {end}\n")
    print(f"- Orders: {s.get('orders_started')} started; outcomes {s.get('outcomes')}")
    print(f"- Completion rate (paid, not cancelled by the customer): {s.get('completion_rate')}")
    print(f"- Delivery minutes (paid → delivered): {s.get('delivery_minutes')}")
    print(f"- Cards declined first: {s.get('declined_first')}, retried: {s.get('retried_card')}; problems: {s.get('problems')}")
    print(f"- Bots: {s.get('stats')}")
    print(f"- Riders (utilisation and pay): {s.get('riders')}")
    print(f"- Waiting for a rider (minutes; overtakes = later orders served 20 s+ sooner): {report['rider_waits']}")
    print("\n| Series | warm avg | last avg | change | max |\n|---|---|---|---|---|")
    for k, g in report["growth"].items():
        print(f"| {k} | {g.get('warm_avg')} | {g.get('last_avg')} | {g.get('change_pct')}% | {g.get('max')} |")
    print(f"\nAlerts (Prometheus): {report['alerts_prometheus']}")
    print(f"Alerts (admin console): {report['alerts_admin_console']}")
    print(f"\nLog error lines: {len(errors)}")
    for k, n in report["log_errors"]["kinds"]:
        print(f"  {n:5d}  {k}")


if __name__ == "__main__":
    main(sys.argv[1])
