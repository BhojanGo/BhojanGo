# Load test: a Boise dinner rush at 3x launch (R21)

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

## What "3x launch" means

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

## Results at 3x launch, as production runs today (1 core_api process)

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

## Realtime: published vs received (0 lost)

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

## The same rush with more core_api, and at 1x

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

## Where core_api's CPU goes (py-spy, 1 minute mid-run)

There's no single slow query. Each request costs about 13 ms of CPU, spread across the stack:

| Share of CPU | What |
|---|---|
| 8% each | The menu (`get_restaurant_menu`: loading it with SQLAlchemy and building the answer) and the home screen (`discover`) |
| 8-11% | Starlette `BaseHTTPMiddleware` layers on every request: security headers (8%), logging and correlation |
| 8-10% | FastAPI finding the route (`routing.matches`): a linear scan of every route, on every request |
| 3-5% | Recomputing the city's kitchen facts for the home screen (below) |
| 5-10% | asyncpg and SQLAlchemy turning rows into objects |

## What was fixed

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

## What's left (smallest fix first)

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

## How much to trust this

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
