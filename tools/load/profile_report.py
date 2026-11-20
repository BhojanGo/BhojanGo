"""R22: core_api's hot paths from py-spy, as CPU milliseconds per request.

    python tools/load/profile_report.py <out dir> [<before out dir>]

Reads path-<name>.txt and paths.json (tools/load/paths.py: one request type at a time)
and profile-core-api.txt (the rush's mixed minute, tools/load/profile.sh). Writes
paths.md (also printed). With a second directory (an earlier run's artifact), each
path's total is shown before and after. Standard library only.

A hot path is "who → where": the innermost frame of our code (core_api/ or shared/,
or the framework layer when there is none) and the library area the CPU was spent in
(SQLAlchemy loading rows, Pydantic, route matching, a middleware...). Its time is
samples / rate / requests: CPU ms per request. py-spy leaves out idle time (waiting
on Postgres or Redis), so this is CPU, not latency; samples in uvloop's native run loop (polling
for I/O, mostly idle when requests come one at a time) are left out too.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

# Where the CPU went: checked from the leaf up; the first frame that matches names the area.
AREAS = [
    (r"^(matches|_match|effective_candidates|_match_low_priority) \(fastapi/routing", "route matching (FastAPI)"),
    (r"\(starlette/routing\.py", "route matching (Starlette)"),
    (r"_find_route_handler \(slowapi", "slowapi middleware: route scan"),
    (r"\(slowapi/", "slowapi middleware"),
    (r"\(prometheus_fastapi_instrumentator/routing", "Prometheus middleware: route scan"),
    (r"\(prometheus", "Prometheus middleware"),
    (r"\(starlette/middleware/base\.py", "BaseHTTPMiddleware (task + copy per request)"),
    (r"\(anyio/", "anyio (BaseHTTPMiddleware streams)"),
    (r"\(starlette/middleware/cors", "CORS middleware"),
    (r"\(structlog/", "logging (structlog)"),
    (r"\(logging/", "logging (stdlib)"),
    (r"\((bcrypt|passlib|argon2)", "password hashing"),
    (r"\((jwt|jose)/", "JWT"),
    (r"\(sqlalchemy/orm/(loading|strategies)", "SQLAlchemy: rows to objects / relationship loads"),
    (r"\(sqlalchemy/sql/(compiler|cache_key)", "SQLAlchemy: compile / cache key"),
    (r"\(sqlalchemy/", "SQLAlchemy: session, engine, other"),
    (r"\(asyncpg/", "asyncpg"),
    (r"\(pydantic", "Pydantic (validate / serialize)"),
    (r"\(fastapi/encoders", "FastAPI jsonable_encoder"),
    (r"\(fastapi/dependencies", "FastAPI dependencies"),
    (r"\(json/", "JSON (stdlib)"),
    (r"\(redis/", "Redis client"),
    (r"\(httpx|httpcore|h11/", "outgoing HTTP"),
    (r"\(socket|ssl\.py", "sockets"),
    (r"\((uvicorn|httptools)", "uvicorn / HTTP parsing"),
    (r"\(starlette/", "Starlette (requests, responses)"),
    (r"\(fastapi/", "FastAPI (other)"),
    (r"\(asyncio/", "event loop (asyncio)"),
]
AREAS_RE = [(re.compile(p), label) for p, label in AREAS]
OURS = re.compile(r"^(\S+) \(((core_api/(?!routing_speed)|shared/(?!middleware/))[^:]+)")  # middleware, routing: "framework"
NAMES = {
    "discover": "Home for an address (`GET /discover`)", "menu": "Menu (`GET /restaurants/{id}/menu`)",
    "quote": "Quote (`POST /pricing/quote`)", "place_order": "Place order (`POST /orders`)",
    "pay_confirm": "Payment confirm (fake gateway event)", "order_status": "Order status (`GET /orders/{id}`)",
    "board": "Kitchen board (`GET /orders/restaurant/{id}`)",
}


def frames(line: str) -> tuple[list[str], int]:
    stack, _, n = line.rstrip("\n").rpartition(" ")
    return [f for f in stack.split(";") if not f.startswith("process ")], int(n or 0)


IDLE = "(waiting in the event loop: uvloop's native run loop, left out)"


def label(fr: list[str]) -> str:
    if fr and fr[-1].startswith("run (asyncio/runners.py"):
        return IDLE  # the loop itself, in C: polling for I/O (idle) and uvloop's own work
    area = "other"
    for f in reversed(fr):
        hit = next((lab for rx, lab in AREAS_RE if rx.search(f)), None)
        if hit:
            area = hit
            break
    else:
        if fr:
            area = re.sub(r":\d+\)", ")", fr[-1])
    who = "framework"
    for f in reversed(fr):
        m = OURS.match(f)
        if m:
            who = f"{m.group(1)} ({m.group(2).split('/')[-1]})"
            break
    return f"{who} → {area}"


def load(path: Path) -> Counter[str]:
    c: Counter[str] = Counter()
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                fr, n = frames(line)
                c[label(fr)] += n
    return c


def path_rows(d: Path) -> dict[str, tuple[dict, Counter[str]]]:
    """Per path: its paths.json entry (plus ``scale``) and samples by hot path, without the idle loop.
    py-spy --nonblocking fails some samples ("Errors: N" in its log); they are spread like the
    others, so each counted sample stands for (samples + errors) / samples."""
    meta = json.loads((d / "paths.json").read_text()) if (d / "paths.json").exists() else {}
    out = {}
    for name, m in meta.items():
        c = load(d / f"path-{name}.txt")
        c.pop(IDLE, None)
        log = d / f"path-{name}.log"
        hit = re.search(r"Samples: (\d+) Errors: (\d+)", log.read_text(errors="replace")) if log.exists() else None
        m["scale"] = (int(hit[1]) + int(hit[2])) / int(hit[1]) if hit and int(hit[1]) else 1.0
        out[name] = (m, c)
    return out


def main() -> None:
    out = Path(sys.argv[1])
    before = path_rows(Path(sys.argv[2])) if len(sys.argv) > 2 else {}
    after = path_rows(out)
    lines = ["# core_api hot paths (py-spy, CPU ms per request)", ""]
    if not after:
        lines.append("No path profiles in this run (paths.json missing).")
    for name, (m, c) in after.items():
        n, rate = m["n"], m.get("rate", 200) / m["scale"]
        total = sum(c.values()) / rate * 1000 / n if n else 0
        head = f"## {NAMES.get(name, name)}: {total:.1f} ms CPU per request"
        if name in before and before[name][0]["n"]:
            bm, bc = before[name]
            btotal = sum(bc.values()) / (bm.get("rate", 200) / bm["scale"]) * 1000 / bm["n"]
            head += f" (before: {btotal:.1f} ms)"
        lines += [head, "",
                  f"{n} requests one at a time: wall p50 {m['p50_ms']} ms, p95 {m['p95_ms']} ms; errors {m['errors'] or 0}.",
                  "", "| # | Hot path (our code → where the CPU went) | ms per request | Share |", "|---|---|---|---|"]
        tot = sum(c.values()) or 1
        for i, (lab, v) in enumerate(c.most_common(10), 1):
            lines.append(f"| {i} | {lab} | {v / rate * 1000 / n:.2f} | {100 * v / tot:.0f}% |")
        lines.append("")
    rush = load(out / "profile-core-api.txt")
    rush.pop(IDLE, None)
    if rush:
        tot = sum(rush.values())
        lines += ["## The rush's mixed minute (profile.sh): share of core_api's CPU", "",
                  "| Hot path | Share |", "|---|---|"]
        lines += [f"| {lab} | {100 * v / tot:.1f}% |" for lab, v in rush.most_common(15)]
    text = "\n".join(lines) + "\n"
    (out / "paths.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
