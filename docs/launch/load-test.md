# Load test: a Boise dinner rush at 3x launch (R21, R22)

## Round 22: core_api made faster (2026-11-20)

**Result: pass.** After R22 (merged with dev's #176 cookie sessions and CSRF, as it will ship), **one core_api
process meets every target at 1x launch** (reads p95 23-86 ms, placing an order p95 50 ms, 0 server errors), and **two
processes meet every target at 3x launch** with 0 server errors, 0 lost realtime updates and all 98 orders delivered
(reads p95 47-329 ms, placing an order p95 232 ms). No process was added
to get there: the same rush costs core_api well under half the CPU it did. Production now runs 2 core_api replicas
for redundancy ([production-config.md](production-config.md#core-api-processes-and-the-database-r22)), and that setup
costs **about $37 a month on Railway at launch** ([below](#what-production-costs-on-railway-r22)).

The scenario is R21's, unchanged (tools/load/rush.js). Only the end of the workflow is new: once the rush is over,
tools/load/paths.py sends one request type at a time while py-spy records core_api, so each path gets its own profile
(tools/load/profile_report.py writes `paths.md`). `-w2` on a `load/*` branch runs 2 core_api processes (as `-w3` did).

### The targets

| Target | Before (R22's own runs, same harness) | After (merged with dev) | |
|---|---|---|---|
| 1x launch, 1 process: reads p95 < 500 ms | 400 ms-1.14 s (board, quote over) | 23-86 ms | **pass** |
| 1x launch, 1 process: place order p95 < 1.5 s | 235-973 ms | 50 ms | **pass** |
| 3x launch, 2 processes: reads p95 < 500 ms | 3.2-13.4 s | 47-329 ms | **pass** |
| 3x launch, 2 processes: place order p95 < 1.5 s | 11.2 s | 232 ms | **pass** |
| 3x launch, 2 processes: 0 errors | 935 failed (0.30%), 26 realtime updates lost | 0 server errors, 0 lost (4 quotes refused as "too far", by the scenario) | **pass** |
| 3x launch, 1 process (reference only) | R21: 16% failed, p95 up to 60 s | 0 server errors; reads p95 246-528 ms (the kitchen board, 528 ms, is over) | reference |

"Reads" are every API read with a target: home, menu, quote, order status, kitchen board, kitchen today, tracking
WebSocket connect. The 422s are the scenario quoting a kitchen just outside its delivery radius; k6 counts
them as failed HTTP requests, and they appear in the before runs too.

### p95 before and after

1x launch (`-s0.34`), one core_api process:

| p95 | R21 | R22 before (1) | R22 before (2) | After (before the merge) | **After, merged with dev** | Target |
|---|---|---|---|---|---|---|
| Home (`GET /discover`) | 1.65 s | 515 ms | 400 ms | 18 ms | **41 ms** | 500 ms |
| Menu | 1.31 s | 572 ms | 434 ms | 7 ms | **23 ms** | 500 ms |
| Quote | 1.57 s | 848 ms | 612 ms | 29 ms | **54 ms** | 500 ms |
| Place order | 1.58 s | 973 ms | 235 ms | 23 ms | **50 ms** | 1.5 s |
| Payment start / confirm | 1.12 / 1.30 s | 537 / 401 ms | 170 / 550 ms | 17 / 17 ms | **29 / 32 ms** | 1.5 s |
| Order status | 1.21 s | 434 ms | 304 ms | 9 ms | **26 ms** | 500 ms |
| Kitchen board / today | 1.85 s / 920 ms | 1.14 s / 659 ms | 593 / 345 ms | 73 / 71 ms | **86 / 84 ms** | 500 ms |
| Tracking WebSocket connect | 895 ms | 158 ms | 121 ms | 33 ms | **35 ms** | 500 ms |
| Failed requests | 1 | 1 | 0 | 0 | **1 (422 "too far")** | |
| Orders placed / delivered | 34 / 34 | 35 / 35 | 35 / 35 | 35 / 35 | 35 / 35 | |
| core_api CPU, average / peak | 59% / 139% | 44% / 125% | 41% / 123% | 16% / 70% | **26% / 98%** | |
| Database connections, peak | 34 | 34 | 34 | 23 | 34 | 100 |
| Run | [44688611848](https://github.com/BhojanGo/BhojanGo/actions/runs/44688611848) | [44703701205](https://github.com/BhojanGo/BhojanGo/actions/runs/44703701205) | [44709569686](https://github.com/BhojanGo/BhojanGo/actions/runs/44709569686) | [44711950354](https://github.com/BhojanGo/BhojanGo/actions/runs/44711950354) | [44724700334](https://github.com/BhojanGo/BhojanGo/actions/runs/44724700334) | |

3x launch, two core_api processes (`-w2`), and one process for reference:

| p95 | 2 processes, before | 2 processes, after (before the merge) | **2 processes, after, merged with dev** | 1 process, R21 | 1 process, after (before the merge) | Target |
|---|---|---|---|---|---|---|
| Home (`GET /discover`) | 12.42 s | 128 ms | **110 ms** | 60.0 s | 303 ms | 500 ms |
| Menu | 12.13 s | 104 ms | **93 ms** | 60.0 s | 267 ms | 500 ms |
| Quote | 13.38 s | 65 ms | **47 ms** | 60.0 s | 279 ms | 500 ms |
| Place order | 11.19 s | 325 ms | **232 ms** | 31.6 s | 562 ms | 1.5 s |
| Payment start / confirm | 7.91 / 9.19 s | 244 / 274 ms | **168 / 218 ms** | 31.0 / 7.53 s | 404 / 444 ms | 1.5 s |
| Order status | 13.12 s | 100 ms | **47 ms** | 1.04 s | 246 ms | 500 ms |
| Kitchen board / today | 6.30 / 3.16 s | 298 / 233 ms | **329 / 261 ms** | 20.2 / 5.62 s | 528 / 378 ms | 500 ms |
| Tracking WebSocket connect | 5.71 s | 199 ms | **241 ms** | 9.52 s | 439 ms | 500 ms |
| Failed requests | 935 (0.30%) | 2 (422 "too far") | **4 (422 "too far")** | 25,989 (16.2%) | 9 (422 "too far") | |
| Realtime updates lost | 26 | 0 | **0** (4,796 locations, 588 statuses, 213 tablet orders) | 0 | 0 | 0 |
| Orders placed / delivered | 97 / 93 | 100 / 100 | **98 / 98** | 33 / 17 | 98 / 98 | |
| core_api CPU, average / peak | 126% / 229% | 52% / 159% | **46% / 164%** | 85% / 141% | 44% / 123% | |
| core_api memory (all its processes) | 480-527 MiB | 378-395 MiB | 388-403 MiB | 288-306 MiB | 196-214 MiB | |
| Database connections, peak | 44 | 44 | 43 | 34 | 34 | 100 |
| Run | [44703701257](https://github.com/BhojanGo/BhojanGo/actions/runs/44703701257) | [44711949423](https://github.com/BhojanGo/BhojanGo/actions/runs/44711949423) | [44724700844](https://github.com/BhojanGo/BhojanGo/actions/runs/44724700844) | [44688854537](https://github.com/BhojanGo/BhojanGo/actions/runs/44688854537) | [44711950530](https://github.com/BhojanGo/BhojanGo/actions/runs/44711950530) | |

- The two R22 "before" runs at 1x are the same code and harness on two runners: they differ by up to 2x, and
  R21's run of the same code was slower again. The after runs beat the best of them by 3-60x on every read. The
  merged run (with dev's cookie session and CSRF layer) is within the same runner-to-runner spread as the
  pre-merge run.
- At 3x on one process (reference), the kitchen board is the one read over target (528 ms): at 3x each new order
  changes a kitchen's board, so the 45 tablets rebuild it often. Two processes take it to 298-329 ms.
- Before R22, two processes at 3x still failed: requests queued for the CPU while holding a database connection, the
  pools ran dry (5,389 `QueuePool limit` errors) and 26 realtime updates were lost.

### Where the CPU went, path by path (top 10 hot paths, before and after)

From the per-path profiles (tools/load/paths.py, after the rush, one request at a time; py-spy at 200 Hz on every
core_api process). The time is **CPU milliseconds per request**: samples / rate / requests, with py-spy's failed
samples spread like the others, and the idle event loop left out. "framework" means no frame of our own code was on
the stack: middleware, routing, and SQLAlchemy's work (it runs in a greenlet, apart from the handler's frames). Before:
run [44709569686](https://github.com/BhojanGo/BhojanGo/actions/runs/44709569686); after: run
[44711950354](https://github.com/BhojanGo/BhojanGo/actions/runs/44711950354).

**Menu (`GET /restaurants/{id}/menu`)**: 4.5 → 0.9 ms of CPU per request (one at a time, wall p50 6.6 → 2.0 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → SQLAlchemy: session, engine, other | 1.07 | 0.12 |
| 2 | framework → route matching (FastAPI) | 0.55 | 0.00 |
| 3 | framework → asyncpg | 0.52 | 0.22 |
| 4 | framework → SQLAlchemy: rows to objects / relationship loads | 0.42 | 0.00 |
| 5 | framework → SQLAlchemy: compile / cache key | 0.23 | 0.01 |
| 6 | framework → FastAPI (other) | 0.21 | 0.03 |
| 7 | framework → other | 0.18 | 0.08 |
| 8 | framework → anyio (BaseHTTPMiddleware streams) | 0.13 | 0.00 |
| 9 | framework → BaseHTTPMiddleware (task + copy per request) | 0.12 | 0.00 |
| 10 | get_with_menu (restaurant.py) → SQLAlchemy: session, engine, other | 0.11 | 0.00 |

**Home for an address (`GET /discover`)**: 2.5 → 1.2 ms of CPU per request (one at a time, wall p50 3.3 → 2.3 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → route matching (FastAPI) | 0.48 | 0.00 |
| 2 | framework → asyncpg | 0.27 | 0.22 |
| 3 | framework → SQLAlchemy: session, engine, other | 0.18 | 0.14 |
| 4 | framework → FastAPI (other) | 0.17 | 0.06 |
| 5 | discover (discover.py) → JSON (stdlib) | 0.14 | 0.00 |
| 6 | framework → uvicorn / HTTP parsing | 0.11 | 0.03 |
| 7 | framework → other | 0.10 | 0.08 |
| 8 | framework → anyio (BaseHTTPMiddleware streams) | 0.09 | 0.00 |
| 9 | discover (discover.py) → Pydantic (validate / serialize) | 0.08 | 0.00 |
| 10 | framework → BaseHTTPMiddleware (task + copy per request) | 0.08 | 0.00 |

**Quote (`POST /pricing/quote`)**: 10.2 → 4.8 ms of CPU per request (one at a time, wall p50 15.8 → 8.3 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → SQLAlchemy: session, engine, other | 1.85 | 0.88 |
| 2 | framework → asyncpg | 1.02 | 0.64 |
| 3 | framework → route matching (FastAPI) | 0.98 | 0.00 |
| 4 | framework → other | 0.63 | 0.40 |
| 5 | framework → event loop (asyncio) | 0.48 | 0.16 |
| 6 | framework → SQLAlchemy: compile / cache key | 0.47 | 0.26 |
| 7 | framework → FastAPI (other) | 0.44 | 0.11 |
| 8 | framework → SQLAlchemy: rows to objects / relationship loads | 0.36 | 0.06 |
| 9 | encode_jwt (auth.py) → JWT | 0.36 | 0.21 |
| 10 | framework → anyio (BaseHTTPMiddleware streams) | 0.27 | 0.00 |

**Place order (`POST /orders`)**: 11.2 → 5.0 ms of CPU per request (one at a time, wall p50 13.9 → 8.9 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → JSON (stdlib) | 2.36 | 0.07 |
| 2 | framework → SQLAlchemy: session, engine, other | 1.49 | 0.92 |
| 3 | framework → asyncpg | 1.14 | 0.75 |
| 4 | framework → route matching (FastAPI) | 0.83 | 0.00 |
| 5 | framework → other | 0.59 | 0.34 |
| 6 | framework → SQLAlchemy: compile / cache key | 0.49 | 0.31 |
| 7 | framework → event loop (asyncio) | 0.28 | 0.24 |
| 8 | framework → FastAPI (other) | 0.28 | 0.27 |
| 9 | candidate (rules.py) → FastAPI (other) | 0.24 | 0.03 |
| 10 | candidates (rules.py) → FastAPI (other) | 0.17 | 0.00 |

**Payment confirm (fake gateway event)**: 7.9 → 3.5 ms of CPU per request (one at a time, wall p50 14.9 → 6.7 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → SQLAlchemy: session, engine, other | 1.71 | 1.07 |
| 2 | framework → asyncpg | 1.03 | 0.63 |
| 3 | framework → route matching (FastAPI) | 0.95 | 0.00 |
| 4 | framework → other | 0.65 | 0.37 |
| 5 | framework → FastAPI (other) | 0.30 | 0.11 |
| 6 | framework → SQLAlchemy: compile / cache key | 0.30 | 0.04 |
| 7 | framework → FastAPI dependencies | 0.23 | 0.04 |
| 8 | framework → anyio (BaseHTTPMiddleware streams) | 0.19 | 0.00 |
| 9 | framework → logging (stdlib) | 0.15 | 0.00 |
| 10 | framework → BaseHTTPMiddleware (task + copy per request) | 0.15 | 0.00 |

**Order status (`GET /orders/{id}`)**: 2.7 → 1.1 ms of CPU per request (one at a time, wall p50 4.1 → 2.4 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → route matching (FastAPI) | 0.57 | 0.00 |
| 2 | framework → asyncpg | 0.28 | 0.29 |
| 3 | framework → SQLAlchemy: session, engine, other | 0.23 | 0.18 |
| 4 | framework → other | 0.20 | 0.08 |
| 5 | framework → FastAPI (other) | 0.18 | 0.06 |
| 6 | framework → anyio (BaseHTTPMiddleware streams) | 0.14 | 0.00 |
| 7 | framework → BaseHTTPMiddleware (task + copy per request) | 0.13 | 0.00 |
| 8 | framework → uvicorn / HTTP parsing | 0.10 | 0.03 |
| 9 | framework → FastAPI dependencies | 0.09 | 0.07 |
| 10 | framework → SQLAlchemy: compile / cache key | 0.08 | 0.02 |

**Kitchen board (`GET /orders/restaurant/{id}`)**: 5.7 → 1.2 ms of CPU per request (one at a time, wall p50 9.3 → 2.3 ms)

| # | Hot path before (our code → where the CPU went) | Before, ms | After, ms |
|---|---|---|---|
| 1 | framework → SQLAlchemy: session, engine, other | 1.10 | 0.25 |
| 2 | framework → asyncpg | 0.83 | 0.29 |
| 3 | framework → route matching (FastAPI) | 0.73 | 0.01 |
| 4 | _as_kitchen_sees_it (orders.py) → Pydantic (validate / serialize) | 0.38 | 0.00 |
| 5 | framework → other | 0.34 | 0.08 |
| 6 | framework → FastAPI (other) | 0.25 | 0.02 |
| 7 | framework → anyio (BaseHTTPMiddleware streams) | 0.19 | 0.00 |
| 8 | _as_kitchen_sees_it (orders.py) → SQLAlchemy: session, engine, other | 0.17 | 0.00 |
| 9 | framework → SQLAlchemy: rows to objects / relationship loads | 0.14 | 0.01 |
| 10 | framework → event loop (asyncio) | 0.12 | 0.02 |

In the rush itself (3x, 2 processes, after), the largest remaining shares are SQLAlchemy and asyncpg running the
one version query each cached request makes (about 11% of core_api's CPU), structlog's two lines per request (5%),
and uvicorn's HTTP parsing (5%). The version query through raw asyncpg would be the next step.

### What was checked, and what changed

| Checked | Found | Done |
|---|---|---|
| Rules loaded on every quote? | Yes: one query per quote (and one per kitchen when the home screen's city facts were rebuilt), every published rule for the scopes, turned into objects each time | Cached per process, keyed by the database's `rules` version: no rule query, and never stale (below) |
| The menu (half of all requests) | Built from the database on every request: 4 queries, ORM objects for every item and option, Pydantic, JSON (4.5 ms of CPU) | The JSON is kept per kitchen until the kitchen, its menu, options or hours change, and sent as is (0.9 ms) |
| The home screen (`/discover`) | Cached per address for 60 s in Redis, but each hit was parsed, validated and serialized again; the review-city check read every city each time | The stored JSON is sent as is; its key carries the versions, so edits show at once; the city rows are cached by version |
| Kitchen board (every tablet, every 4 s) | Up to 100 whole orders, a query per customer and rider name (N+1) | Names in one query; the JSON kept per kitchen until its orders or a name on them change |
| Availability (quote, order, tablet "today", home) | A kitchen's city, time zone and hours: 7-9 queries each time | Cached by version (the kitchen and the markets) |
| Starlette `BaseHTTPMiddleware` | Correlation id, request logging and slowapi: a task and memory streams per request | Correlation and logging rewritten as pure ASGI (same headers and log lines); slowapi's middleware removed: it only applies default limits and there are none (the sign-in limits are decorators and work without it; their tests pass) |
| Route matching | FastAPI tried every route of every router (about 500) before the matching one; slowapi and the Prometheus middleware scanned them again | Each router first checks the static start its routes share (core_api/routing_speed.py; a test checks every route resolves the same); the Prometheus route name is remembered per path |
| Token checks on each request | An RS256 signature check on every authenticated request (tablets, tracking) | A verified token is remembered until it expires, and only while its signing key is still trusted |
| Password hashing on each request? | No: only at sign-in and password changes | Nothing to do |
| Blocking calls on the event loop? | None on these paths (Redis and Postgres are async; py-spy shows no blocking I/O) | Nothing to do |
| Large responses (Pydantic, JSON) | Menu, home and board were validated and serialized on every request | Sent as stored JSON (above). Responses aren't gzipped: that would cut egress, not CPU |
| Tax and provider calls in the quote path | The stack uses the fake tax provider (no network). In production a US quote calls **Stripe Tax** once per quote (idempotency key `taxcalc:<quote id>`): one HTTPS round trip, typically 100-300 ms of waiting, not CPU | Not cached: a tax calculation belongs to one quote. The quote limit (60 a minute per person) bounds it. Expect production's quote p95 to be this much higher than the stack's |
| OpenSearch at localhost:9200 | Connection errors at start-up only (the index check), on no rush path | Left as is |
| uvicorn workers | One process; `--workers` not set in production | `core_api/start.sh`: one process per CPU the container may use (cgroup limit), at most 2; 2 replicas in production |
| A bug found on the way | With 2 processes on a fresh dev key volume, each process could keep its own dev signing key (one replaced the other's file), so a token from one failed in the other (e2e: 401 right after sign-in) | The dev key is now created only if absent (`shared/jwt_keys.py`). Production uses `JWT_PRIVATE_KEY` and never had this |

### Every cache, and how it learns of an edit

The database keeps the versions (migration `0040_cache_versions`): triggers on the tables below insert a row in the
writing transaction, so a new version is visible exactly when an edit commits, whoever made it (the API, the worker,
a script, psql), and never if it rolls back. Each cached value is stored under the versions read before it was
computed, and used only while they are still current: **an edit shows on the very next request, in every process**.
Each use costs one small query (the versions). A session that has written never fills a cache (its edit might roll
back). `CACHE_VERSIONED=false` turns them all off.

| Cache (per process) | Holds | Invalidated by (version scope: tables) | Also expires |
|---|---|---|---|
| Menu (`GET /restaurants/{id}/menu`) | the JSON | `kitchen:<id>`: restaurants, menu_categories, menu_items, option_groups, options, menu_item_option_groups, store_hours, store_hour_overrides; `kitchen:*` | when the first "sold out today" ends; 5 min backstop |
| Who may see a review city (R19/R20) | every city's code, name, country and settings | `markets`: countries, regions, cities, zones | - |
| A kitchen's market (city, time zone, service hours, licence rule) | values | `kitchen:<id>`, `markets` | 5 min backstop |
| A kitchen's hours and day overrides | values | `kitchen:<id>` | 5 min backstop |
| A kitchen's city code | value | `kitchen:<id>`, `markets` | 5 min backstop |
| Published rules for a set of scopes | the rules (the quote's time is applied on each use) | `rules`: rules | 5 min backstop |
| Cities' time zones | values | `markets` | 5 min backstop |
| Kitchen board (`GET /orders/restaurant/{id}`) | the JSON, per kitchen, page and limit | `orders:<id>`: orders; `people`: a user's name changed or a user deleted; `markets` | 5 min backstop |
| Home for an address (`GET /discover`, Redis, existing) | the JSON | its key carries `kitchens` (any kitchen edit), `kitchen:*`, `rules`, `markets` | 60 s, as before (open now and offers depend on the time) |
| Home's city facts (existing, per process) | listed kitchens, availability, rules, offers | the same versions, in its key | 20 s (`DISCOVER_FACTS_SECONDS`), as before |
| Verified access tokens | claims | a retired signing key; the token's own expiry | at most 4,096 kept |

Money: a quote reads the rules at the current `rules` version, in its own transaction, so a rule approved before the
quote is in it. Prices are never cached for a quote: it reads the items and options from the database
(catalog.service.cart), as before; the cached menu is what customers browse, and any price edit changes its version.
Review accounts: the cached menu and board are the same for everyone who may see them, and who may see them is worked
out for each viewer before the cache is used; a review account's home screen is never cached (as in R20).

Tests: `backend/core_api/integration/test_r22_caches.py` edits each kind of thing, through the API and behind its back
(SQL in another connection), and expects the next request to show it: a menu price, an option price, sold out today,
the kitchen's details, a city made review-only (its kitchen's cached menu turns 404), a rule approved by a second
admin (the next quote has it) and then paused, a kitchen pause and a closed day (quotes refused at once), an admin
pause on the home screen, an order and a customer's name on the kitchen board, and a session that wrote never filling
a cache. `backend/core_api/tests/test_r22_caches.py` and `test_routing_speed.py` cover the rest without a database.

### What production costs on Railway (R22)

Prices from Railway's pricing page, <https://docs.railway.com/reference/pricing/plans>, read on 2026-11-20: **$20 per
vCPU per month, $10 per GB of RAM per month, $0.15 per GB of volume per month, $0.05 per GB of egress**. The Pro plan
is $20 a month and includes $20 of usage (Hobby: $5, including $5). Usage is billed by the minute on what each
container uses, not on its limit.

Measured CPU (in vCPUs) and memory, from samples.csv of the merged after runs (every 5 s; 100% CPU = 1 vCPU). core_api's
CPU follows the load, not the number of processes; its memory is per process, so production's 2 replicas x 2
processes = 4 processes count 4 x the per-process memory.

| Service | 1x launch, average (run 44724700334) | 3x, average (run 44724700844) | 3x, peak (run 44724700844) |
|---|---|---|---|
| core-api CPU | 0.262 | 0.456 | 1.642 |
| core-api memory | 4 x 180 = 720 MiB | 4 x 194 = 776 MiB | 4 x 202 = 806 MiB |
| realtime | 0.076 vCPU, 100 MiB | 0.077, 129 MiB | 0.450, 142 MiB |
| worker | 0.060, 108 MiB | 0.048, 109 MiB | 0.312, 122 MiB |
| postgres | 0.053, 112 MiB | 0.136, 157 MiB | 0.644, 221 MiB |
| redis | 0.016, 11 MiB | 0.013, 16 MiB | 0.048, 24 MiB |
| **Total** | **0.467 vCPU, 1,051 MiB (1.026 GB)** | **0.730 vCPU, 1,187 MiB (1.159 GB)** | **3.096 vCPU, 1,315 MiB (1.284 GB)** |

Egress: the 1x rush sent 1.39 GB to clients in 38 minutes (k6 `data_received`), 3x sent 4.47 GB. Assumed: two hours a
day at that rate (lunch and dinner), 30 days: 1.39 / 38 x 120 x 30 = **132 GB** at 1x, 4.47 / 38 x 120 x 30 =
**424 GB** at 3x. Volume: Postgres's 10 GB volume (railway.ts), billed as 10 GB (the most it can hold).

```
monthly = max(plan fee, usage)          (Pro: the $20 fee includes $20 of usage; above that, usage is billed)
usage   = 20 x vCPU + 10 x GB RAM + 0.15 x 10 GB volume + 0.05 x GB egress

launch, every hour like the 1x rush:   20 x 0.467 + 10 x 1.026 + 1.50 + 0.05 x 132 =  9.34 + 10.26 + 1.50 +  6.60 = $27.70
busy month, every hour like 3x:        20 x 0.730 + 10 x 1.159 + 1.50 + 0.05 x 424 = 14.60 + 11.59 + 1.50 + 21.20 = $48.89
ceiling, 3x's peak all month long:     20 x 3.096 + 10 x 1.284 + 1.50 + 0.05 x 424 = 61.92 + 12.84 + 1.50 + 21.20 = $97.46
```

Not measured (not in the load test): **web and admin** (Next.js). Assumed 0.1 vCPU and 0.25 GB each:
2 x (20 x 0.1 + 10 x 0.25) = **$9.00**. With them, production on Pro is **about $37 a month at launch** ($27.70 + $9.00
= $36.70), **about $58 in a busy month at 3x** ($57.89), and at most **about $106** if 3x's peak lasted all month
($106.46). (The pre-merge runs gave $32.92, $59.59 and $112.50: the runner-to-runner spread.) Assumptions: the measured averages hold all month (quiet nights cost less, so this overstates launch); the
runner's CPUs are comparable to Railway's vCPUs; the Postgres volume is full; egress is two rush hours a day; the
bucket's storage and requests (photos) are not included. Before R22 the same 3x rush on two processes used 2.4 times
core_api's CPU (126% average against 46%) and still failed.

## Round 21: the first run (2026-11-20)

**Result: fail.** On 2026-11-20, with core_api as one process (as on Railway today), API reads and placing an order
were far over target at 3x launch: p95 of 1-60 s, and 16% of requests failed. Realtime itself passed: 0 updates
lost, and rider pings at p95 7 ms. **Even at 1x launch, one core_api process misses the read targets** (p95
0.9-1.9 s, though with no errors). With 3 core_api processes, 3x ran with 0 errors, 0 lost updates and every order
delivered, but p95 stayed at 1.1-3.2 s on the shared runner.

The cause is core_api's CPU, not the database. One Python process spends about 13 ms of CPU per request, and the
rush's browsing alone asks for about 150 requests a second. Postgres averaged 1-2 active queries throughout. One
cause was fixed here (the home screen's query count, below). The rest is named below, with the smallest fix first.

To rerun, push to a `load/*` branch (`load/<name>-w3` runs 3 core_api processes, `-s0.34` runs 1x launch), or use
Actions > "Load test (throwaway stack)". The stack is built on the GitHub runner and thrown away. QA and production
are never touched: tools/target_guard.py runs first, and k6 refuses any hosted API. The results are in the run's
`load-test` artifact: report.md, summary.json (k6), samples.csv (every 5 s), realtime.json and
profile-core-api.txt (py-spy).

### What "3x launch" means

| Who | Launch estimate | Tested (3x) | Where the estimate comes from |
|---|---|---|---|
| Orders at the peak | 100 an hour | **300 an hour** (5 a minute for 20 minutes) | Srini's. The docs only assume 60 an hour for the pilot (docs/load/report.md), and the rehearsal's rush was 120 (docs/load/soak-report.md). 300 is the stricter |
| Quotes | about 5 per order | **25 a minute** | docs/load/report.md (people changing their bag) |
| People browsing the app | about 670 | **2,000** | Srini's (the docs only have about 200 invited pilot customers). Each person opens the home screen for their address, then menus, spending 5-15 s on each screen |
| Delivery partners online | **25** | **75**, GPS every 5 s | The docs plan 25 for Boise (STATUS #38, rehearsal #55), so 75, not 40 |
| Kitchen tablets on live updates | **15** | **45**, board every 4 s | The pilot plan is 10-15 kitchens (docs/load/report.md), so 45, not 25. The stack has 21 Boise kitchens, so each has 2-3 tablets; the first one accepts and cooks |
| Customers tracking an order | | about 50 at once | Every order, from paid to delivered (WebSocket, plus the app's 15 s status poll) |

What each one does (tools/load/rush.js):
- **Customers** quote, place the order, start the payment and confirm it, then track it until it's delivered. The
  confirm is the fake gateway's signed event, the same path a real webhook takes.
- **Kitchens** see the order on the board, accept it and cook for 3-5 minutes.
- **Riders** get the offer over `/ws/rider` and accept it. They ride (pinging every 5 s), pick up when the order is
  ready, and hand it over with the customer's PIN.

60 customer accounts place the orders. That's under 1 quote a minute each, far below the per-person quote limit in
#168, so the limit is left on.

### Results at 3x launch, as production runs today (1 core_api process)

Run [44688854537](https://github.com/BhojanGo/BhojanGo/actions/runs/44688854537): 20 minutes of orders, then the
deliveries finish.

| Request | p50 | p95 | p99 | Target (p95) | |
|---|---|---|---|---|---|
| Quote (`POST /pricing/quote`) | 4.69 s | 60.0 s | 60.0 s | 500 ms | **fail** |
| Place order (`POST /orders`) | 3.02 s | 31.6 s | 32.1 s | 1.5 s | **fail** |
| Payment start (`POST /payments/initiate`) | 2.12 s | 31.0 s | 31.5 s | 1.5 s | **fail** |
| Payment confirm (gateway event applied) | 2.00 s | 7.53 s | 26.2 s | 1.5 s | **fail** |
| Order status (`GET /orders/{id}`) | 13 ms | 1.04 s | 3.27 s | 500 ms | **fail** |
| Home for an address (`GET /discover`) | 54.4 s | 60.0 s | 60.0 s | 500 ms | **fail** |
| Menu (`GET /restaurants/{id}/menu`) | 12.7 s | 60.0 s | 60.0 s | 500 ms | **fail** |
| Kitchen board / today | 50 / 22 ms | 20.2 / 5.6 s | 60 / 60 s | 500 ms | **fail** |
| Rider location ping (realtime) | 3 ms | 7 ms | 29 ms | 500 ms | pass |
| Rider state poll (realtime) | 2 ms | 5 ms | 11 ms | 500 ms | pass |
| Tracking WebSocket connect | 7.53 s | 9.52 s | 9.92 s | 500 ms | **fail** (realtime waits for core_api) |
| Realtime delivery: rider fix to tracking screen | 4 ms | 27 ms | 67 ms | | |
| Realtime delivery: status change to tracking screen | 1 ms | 3 ms | 4 ms | | |

- **Errors:** 25,989 of 160,873 requests failed (16.2%), as 500s and 60 s timeouts. core_api logged 91,076
  `QueuePool limit ... connection timed out` errors. Requests held their database connection while waiting for the
  CPU, so the pool ran dry although Postgres was idle. realtime logged 1,932 timeouts calling core_api. Only 33
  orders were placed (100 were due), and 17 were delivered.
- **Database connections:** peak 34 (core_api's pool of 30, plus the worker), average 26, of 100 allowed. Active
  queries averaged 1.2 (peak 8).
- **CPU** (100% = one core): core_api averaged 85% (peak 141%) and was at its one core in 61% of the samples.
  realtime averaged 15% (peak 95%), Postgres 9% (64%), worker 6% and Redis 2%. The runner as a whole was 38% busy
  on average.
- **Memory:** core_api 288-306 MiB, Postgres 204-278 MiB, realtime 139-153 MiB, worker 108-121 MiB, Redis
  13-22 MiB, flat through the run. k6 itself used 1.9-2.1 GiB.

### Realtime: published vs received (0 lost)

Every update is counted at both ends. Published updates are:
- each rider ping whose answer names an order (realtime published a location for it)
- each status a kitchen or rider set
- each order that reached "placed"

Received updates are what the customers' tracking sockets and the kitchen tablets' boards got. A socket only owes
updates published while it was open. For statuses, the update must also come at least 10 s before the socket closed,
because statuses travel through the outbox and the event bus.

| Updates | 3x, 1 process | 3x, 3 processes | 1x, 1 process |
|---|---|---|---|
| Rider locations owed to tracking sockets / received / **lost** | 153 / 153 / **0** | 4,819 / 4,819 / **0** | 1,130 / 1,130 / **0** |
| Order statuses owed / received / **lost** | 8 / 8 / **0** | 588 / 588 / **0** | 144 / 144 / **0** |
| New orders owed to tablets / seen / **lost** | 69 / 69 / **0** | 210 / 210 / **0** | 24 / 24 / **0** |
| New order to seen on a tablet: p50 / p95 | 78 s / 273 s | 2.2 s / 5.2 s | 1.8 s / 4.6 s |
| Duplicates | 0 | 0 | 0 |

**Pass: 0 lost.**
- At 3x on one process, few updates were owed, because few orders got far enough. The 3-process run is the real
  test of realtime: 4,819 locations to 98 orders.
- The tablets saw every order, but late when core_api was overloaded. The board is a 4 s poll of core_api, not a
  push.
- An earlier run counted 12 lost locations, but the test itself caused them. A slow status poll blocked the k6 VU,
  and closing the socket then dropped messages it had already received. The tracker now closes only once its socket
  is quiet, and the rerun lost none.

### The same rush with more core_api, and at 1x

| p95 | 3x, 1 process | **3x, 3 processes** | **1x, 1 process** | Target |
|---|---|---|---|---|
| Quote | 60.0 s | 3.24 s | 1.57 s | 500 ms |
| Place order | 31.6 s | 1.69 s | 1.58 s | 1.5 s |
| Payment start / confirm | 31.0 / 7.53 s | 1.57 / 1.53 s | 1.12 / 1.30 s | 1.5 s |
| Order status | 1.04 s | 2.08 s | 1.21 s | 500 ms |
| Home / menu | 60 / 60 s | 2.80 / 2.62 s | 1.65 / 1.31 s | 500 ms |
| Kitchen board | 20.2 s | 1.95 s | 1.85 s | 500 ms |
| Failed requests | 16.2% | 0.00% (5) | 0.00% (1) | |
| Orders placed / delivered | 33 / 17 | 98 / 98 | 34 / 34 | |
| core_api CPU, average / peak | 85% / 141% | 150% / 297% | 59% / 139% | |
| Database connections, peak | 34 | 64 | 34 | 100 |
| Runner CPU busy, average / peak | 38% / 54% | 54% / 93% | 29% / 56% | |
| Run | [44688854537](https://github.com/BhojanGo/BhojanGo/actions/runs/44688854537) | [44688858654](https://github.com/BhojanGo/BhojanGo/actions/runs/44688858654) | [44688611848](https://github.com/BhojanGo/BhojanGo/actions/runs/44688611848) | |

- **3 processes** fixed the failures and the lost orders, but not the latency. The runner was 93% busy at its peak
  (3 core_api processes, Postgres, realtime and k6 on 4 vCPUs), so this run doesn't show what 3 processes would do
  on their own CPUs.
- **1x on one process** had no errors and delivered every order, but every core_api read was over 500 ms at p95.
  core_api averaged 59% of a core, but it hit 100% in bursts (a tenth of the 5 s samples), and requests queued
  behind it.

### Where core_api's CPU goes (py-spy, 1 minute mid-run)

There's no single slow query. Each request costs about 13 ms of CPU, spread across the stack:

| Share of CPU | What |
|---|---|
| 8% each | The menu (`get_restaurant_menu`: loading it with SQLAlchemy and building the answer) and the home screen (`discover`) |
| 8-11% | Starlette `BaseHTTPMiddleware` layers on every request: security headers (8%), logging and correlation |
| 8-10% | FastAPI finding the route (`routing.matches`): a linear scan of every route, on every request |
| 3-5% | Recomputing the city's kitchen facts for the home screen (below) |
| 5-10% | asyncpg and SQLAlchemy turning rows into objects |

### What was fixed

1. **The home screen made about 130 queries per address** (`backend/core_api/modules/catalog/api/v1/discover.py`).
   - *Before:* an uncached `GET /discover` checked each of Boise's 21 kitchens one by one, for every new address:
     its hours, its city and timezone, and its rules (about six queries each). The first 3x run spent most of
     core_api's one core on this. The home screen's p50 was 55 s, and 104,000 tracebacks were logged.
   - *Now:* the part that doesn't depend on the address is computed once per city and zone every 20 s in each process
     (`_city_facts`, `_compute_facts`). That part is which kitchens are listed and open, and their rules, offers and
     photos. An address only adds distances and delivery fees, with no queries.
   - Answers stay as fresh as before, because the per-address answer was already cached for 60 s. Review accounts
     always get fresh answers. The time is a setting, `DISCOVER_FACTS_SECONDS` (`backend/shared/config.py`; 0 works
     as before).
   - On its own, this fix doesn't rescue 3x on one process: the menus and everything else still need more CPU than
     one process has.
2. **The load test's own setup** (`tools/soak/setup.py`): riders past 8 now get 6xx phone numbers. With 75 riders,
   the 2xx numbers collided with the demo riders' numbers.

### What was left (R22 did 1-3, above; 4 is not needed now)

1. **Run more than one core_api process in production.** Today Railway runs one replica of one uvicorn process
   (`.railway/railway.ts`; QA caps it at 1 vCPU). That already misses the read targets at 1x launch.
   - *Smallest fix:* set `numReplicas: 2-3` for core-api in railway.ts (or `--workers N` in its start command).
     Size each pool so they all fit in Postgres' 100 connections (10 + 10 each, as this test did).
   - *Cost:* more on Railway, about 300 MiB and up to a core per process, billed by use. That's Srini's decision.
   - The code is ready for it: the order timers are already safe with several replicas.
2. **Cache the menu.** Half of all requests are `GET /restaurants/{id}/menu`, and the answer is the same for
   everyone.
   - *Fix:* cache it in Redis for 30-60 s, like the home screen. Clear it when the kitchen edits the menu or marks
     something sold out (the quote still checks availability).
   - *Not done here:* the menu has many write paths to clear it from, and the integration tests read menus right
     after editing them.
3. **Cheaper requests.** Turn the security, logging and correlation middlewares into plain ASGI middleware:
   Starlette's `BaseHTTPMiddleware` costs a task and a copy per request. Then look at route matching (8-10%).
4. **Smaller ones:**
   - When several requests miss the city facts at once, compute them once (a lock per city and zone).
   - core_api tries to reach OpenSearch at localhost:9200 on some requests (12 connection errors per run; OpenSearch
     isn't in compose).

Then rerun 3x with 2-3 processes, with the same targets.

### How much to trust this

- **The runner is 4 vCPU and 16 GB, shared by the whole stack and k6.** k6 used 1.9-2.7 GiB and up to 2 cores at
  its peaks, and py-spy ran for one minute in the middle. Production gives each service its own CPU, so this test is
  pessimistic when the runner is busy, as in the 3-process run. The 1-process runs weren't held back by the runner:
  it was 38% busy while core_api was pinned at one core. One process is one core, however big the machine is.
- **Production is Railway**, with one replica per service. railway.ts sets no replica count and no CPU caps for
  production. QA is capped at 1 vCPU / 1 GiB for core-api, and 0.5 vCPU / 0.5 GiB for realtime and worker.
  Railway's network, Postgres volume and Redis add latency this test doesn't have.
- **Test settings:** the stack is `infra/docker/load.compose.yaml` over the dev compose file.
  - People sign in from their own address (`CLIENT_IP_HEADER=X-Real-IP`, as on Railway).
  - Tokens last 2 hours, so there's no refresh during the run.
  - The fake gateway doesn't pay by itself: k6 confirms each payment and times it. Payments never reach Stripe.
  - The demo rider is off.
- **The browsing model is ours:** each person opens a screen every 5-15 s from their own address, about 0.1
  requests a second per person. Slower readers would mean fewer requests.
- **Realtime latencies are measured in k6.** A blocked VU (a slow status poll) delays what its socket got, so when
  core_api is overloaded the realtime p99s include that wait.
- **Not covered:** the website, push and SMS, a real payment provider, batching (off for the launch), riders passing
  on offers, and Postgres on its own disk.

Earlier runs of this test:
- [44672984091](https://github.com/BhojanGo/BhojanGo/actions/runs/44672984091): before the home screen fix. Its
  artifact was deleted because the token scrub failed; the scrub is fixed now.
- 44678303464 and 44683355626: 1 process, after the fix.
- 44683359037: 3 processes, before the tracking-socket fix.
