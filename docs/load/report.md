# Load test at 10× pilot peak (P24)

**Result: pass.** On 2026-11-12, every key path's p95 stayed under 500 ms (the slowest was 83 ms) at ten times the
expected pilot peak, held for five minutes. There were 0 failed requests out of 25,735, and 1,200 tracking WebSocket
sessions. Getting there took three fixes in realtime (below). Before them, rider location pings and tracking sockets
failed under load.

Rerun with `tools/load/run.sh` on `make dev`. The raw k6 summary is in [summary-2026-11-12.json](summary-2026-11-12.json).

## What "10× pilot peak" means

The pilot (tracker, Phase 4) is 10–15 kitchens, 20–30 riders and about 200 invited customers in one zone. Assumed
dinner peak: about 60 orders an hour, about 5 quotes per order, 30 riders each sending a GPS fix every 5 s, and about
20 orders being tracked at once.

| Path | Pilot peak | Tested (10×) |
|---|---|---|
| Place order (quote → order → payment → order) | 1 / min | **10 / min** |
| Quote (`POST /pricing/quote`) | ~0.1 / s | **1 / s** |
| App browsing (kitchens, kitchen page, menu) | 0.5 / s | **5 / s** (15 req/s) |
| Web key screens (home, city, kitchen page) | 0.3 / s | **3 / s** (9 req/s) |
| Rider location pings (realtime) | 6 / s | **60 / s** |
| Tracking WebSockets open at once (realtime) | 20 | **200**, opened over 30 s, each reconnecting every ~55 s |

## Results: p95 under 500 ms (k6, 5 minutes)

| Request | p50 | p95 | p99 | max |
|---|---|---|---|---|
| Kitchens list (`GET /restaurants`) | 4 ms | **14 ms** | 23 ms | 275 ms |
| Kitchen page (`GET /restaurants/by-slug/…`) | 6 ms | **22 ms** | 36 ms | 82 ms |
| Menu (`GET /restaurants/{id}/menu`) | 14 ms | **32 ms** | 50 ms | 402 ms |
| Quote (`POST /pricing/quote`) | 46 ms | **83 ms** | 132 ms | 161 ms |
| Place order (`POST /orders`) | 28 ms | **71 ms** | 360 ms | 596 ms |
| Payment (`POST /payments/initiate`) | 13 ms | **31 ms** | 275 ms | 446 ms |
| Order / tracking screen (`GET /orders/{id}`) | 7 ms | **17 ms** | 42 ms | 66 ms |
| Rider location ping (realtime) | 3 ms | **9 ms** | 24 ms | 136 ms |
| Tracking WebSocket connect (realtime) | 3 ms | **20 ms** | 44 ms | 99 ms |
| Web home | 7 ms | **18 ms** | 48 ms | 1.5 s (first render) |
| Web city page | 1 ms | **7 ms** | 16 ms | 83 ms |
| Web kitchen page | 6 ms | **16 ms** | 27 ms | 223 ms |

The run made 25,735 HTTP requests (71 a second) with **0 failures**, and 2,593 WebSocket messages were delivered.

## What was over 500 ms, and the fixes

The first run at 10×: 67% of requests failed. Rider pings had a p95 of 4.2 s (91% failed with 500), and tracking
sockets took a p95 of 5.8 s to connect (93% failed). Running each path on its own showed that core_api was fine
(p95 ≤ 112 ms) and realtime was not.

1. **Redis connections ran out in realtime.** Every tracking or rider WebSocket opened its own Redis pub/sub
   connection. At 200 sockets the pool hit its limit (`MaxConnectionsError: Too many connections`), and every
   other Redis call failed with it, location pings included.
   *Fix:* one shared pub/sub connection per realtime process (`backend/realtime/app/core/hub.py`). It subscribes to
   an order's channel when the first watcher arrives and unsubscribes when the last leaves, and hands each message to
   that channel's sockets. Unit test: `realtime/tests/test_hub.py`.
2. **Duplicate tracking messages (found on the way).** Each socket's listener broadcast to every socket on the order.
   With two people watching one order (customer app and web, or ops), each update went out twice to each.
   *Fix:* through the hub, each socket sends only to itself.
3. **A burst of trackers called core_api one by one.** Each tracking connect made a fresh signed call to core_api to
   check who may watch.
   *Fix:* use dispatch's cached copy if it is under 15 s old; status changes already refresh it.
   Also: the shared Redis client now has an explicit pool (`REDIS_MAX_CONNECTIONS`, default 100) that waits up to 5 s
   for a free connection instead of failing.

After the fixes, the same mix had 0 failures and the p95s above.

## How much to trust this

- **Where it ran:** `make dev` on one Windows laptop (8 CPUs, Docker Desktop). Each service was one process, with
  Postgres, Redis and LocalStack in containers, and the `make observe` stack running with tracing on, as it would be
  in production. Production runs several tasks per service on bigger databases. These numbers are a floor, not a
  promise.
- **Not covered:** real payment providers (the fake one answers at once), push and SMS delivery, and the Android
  apps' own rendering. Dispatch's offer loop ran, but riders weren't accepting orders during the test.
- **The pilot assumptions are ours.** If the pilot's dinner peak is far above 60 orders an hour, rerun with the
  rates changed at the top of `tools/load/pilot.js`.
