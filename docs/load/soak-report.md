# Pilot dress rehearsal: a 2-hour Boise dinner rush

**Result: pass, with three fixes.**
- **The run.** On 2026-11-13, `make dev` + `make observe` carried a simulated two-hour Boise dinner rush: 150 orders,
  5 kitchens, 8 riders.
- **Completion and errors.** Every paid order that the customer didn't cancel was delivered (130 of 130). Nothing
  returned a server error, and the logs had no error lines.
- **Memory and connections** stayed flat.
- **Alerts.** Both that fired did their job and resolved on their own.

The rehearsal found three things worth fixing, all fixed in this PR:

1. Dispatch wasn't oldest-first.
2. Servers closed idle connections after 5 s.
3. The payment alert paged on ordinary card declines.

A short re-run confirms the fixes ([below](#after-the-fixes-60-minute-re-run)).

It also showed that **8 riders can't carry this rush**: orders queued for a rider for up to 52 minutes. That's a
staffing number for the pilot, not a bug (see [What it means for the pilot](#what-it-means-for-the-pilot)).

Rerun it with `tools/soak/run.sh` (needs `make dev` and `make observe`). The output goes to `tools/soak/out/<time>/`.

## The scenario

Everyone is a bot doing what the apps do, over the real APIs and WebSockets (`tools/soak/soak.py`):

| Who | What they do |
|---|---|
| **40 customers** | Quote, order and pay. **8%** of first cards decline: half of those customers try another card, the other half walk away and the payment timeout cancels the order. **4%** cancel after paying, before the kitchen accepts. They watch the tracking WebSocket until the order ends. **6%** report a problem after delivery |
| **5 kitchens** (one partner account, as in the seed) | Accept after 20–75 s, then cook for 4–9 minutes: "almost ready" at 60%, "ready" at the end |
| **8 riders** | Online for the whole shift, sending GPS every 10 s. They pass on **12%** of offers, ride to the kitchen, wait at the counter, pick up, ride to the customer and hand over with the customer's PIN |

**Timing.** Orders follow a dinner curve: quiet for the first 40 minutes, peaking between minutes 60 and 95, then
tapering off. Ride legs are shortened to 1.5–3.5 minutes so the run fits in two hours. **Delivery times below are
compressed;** what matters is how they change when riders run short.

**Measurements**
- Once a minute: memory and CPU per container, Postgres connections, Redis clients, memory and keys, and
  connections into realtime and core_api (`tools/soak/sample.sh`).
- Afterwards: Prometheus's alert history, the alerts shown in the admin console, and every error line from the
  services' logs.

## Results (2 hours, 150 orders)

| | |
|---|---|
| **Completion rate** | **100%**: 130 of 130 paid orders that the customer didn't cancel were delivered |
| Orders | 150 started; 130 delivered; 3 cancelled by the customer (refunded); 6 abandoned after a declined card (the payment timeout cancelled them); 11 never placed (below) |
| Card declines | 12, of which 6 retried and were delivered |
| Problem reports | 5: 1 refunded automatically, 4 became tickets |
| Offers | 145 made, 15 passed on, 130 accepted |
| **Median delivery time** | **12.1 min** from payment to hand-over (quartiles 10.5 / 12.1 / 17.7, p90 28.5, max 61.5; compressed travel) |
| Waiting for a rider | median 1.7 min, p90 18.1, **max 52.4**. In **646 pairs** an order that started looking later got a rider sooner |
| Server errors (5xx) | **0** |
| Error lines in the logs (core-api, realtime, worker, web, admin, Postgres, Redis) | **0** |
| Dropped connections | 5 "server disconnected without a response" on reused connections (fixed: below) |
| Tracking | 9,740 WebSocket messages; 0 socket errors |

**The 11 orders never placed** were the bots' fault, not the app's. Their baskets met the kitchen's minimum but not
the delivery zone's ($15–$20), and the quote said so (`CANNOT_QUOTE`), which is what the app shows a customer. The bot
now adds an item and quotes again, as a customer would.

### Memory and connections

The first column averages minutes 10–30 (warmed up); the second averages the last 20 minutes.

| Series | Warm | Last 20 min | Max | Verdict |
|---|---|---|---|---|
| core-api memory | 150 MiB | 159 MiB | 170 MiB | flat (+5%) |
| realtime memory | 97 MiB | 103 MiB | 114 MiB | flat (+6%) |
| worker memory | 119 MiB | 120 MiB | 131 MiB | flat |
| web / admin memory | 46 / 40 MiB | 46 / 40 MiB | 57 / 50 MiB | flat |
| Postgres memory | 84 MiB | 119 MiB | 121 MiB | Shared buffers filling as tables are read; capped by `shared_buffers` (128 MB). Not a leak |
| Postgres connections | 7 | 8 | 8 | flat (pools) |
| Redis clients | 6 | 6 | 6 | flat (one pub/sub per realtime process, from P24) |
| Redis memory / keys | 2.7 MiB / 1,509 | 3.5 MiB / 1,930 | 3.5 MiB | About 3 keys per order: tracking trail, order info, offers, all with expiry times. The only keys without expiry are the 11 riders' states |
| Connections into realtime | 9 | 16 | 40 | Follows the orders being tracked (40 at the peak backlog); back down as they finished |
| CPU | | | | core-api 8.6% average (65% peak), realtime 6.1%, worker 6.7%, Postgres 1.8% |

### Alerts

| Alert | Fired | For | Right call? |
|---|---|---|---|
| **OrdersWithoutRider** (Boise) | 05:52 → 06:37 | 44 min | **Yes.** All 8 riders were busy and ready orders waited (below). It showed in the admin console and resolved by itself |
| **PaymentFailures** (Boise) | 05:53 → 06:14 | 35 min | **No: a false alarm.** It fired on 3+ failures in 15 minutes. At a rush, ordinary declines get there on their own. Fixed: it now needs 30% of payments to fail as well |

No error-spike or stale-KPI alerts fired.

## What it found, and the fixes

**1. Dispatch wasn't oldest-first.**
- *Before.* Orders waiting for a rider each retried on their own 15-second timer, so whichever timer came up next got
  the next free rider. A rider who had just finished also sat idle until a timer came up.
- *In the rush.* Some orders waited 30–50 minutes while newer ones got riders within a minute: 646 overtakes, the
  52-minute maximum wait, and the 61-minute maximum delivery.
- *Fix* (`backend/realtime/app/services/dispatch.py`):
  - Waiting orders are kept in the order they started looking (`dispatch:waiting`).
  - The moment a rider is free (going online, finishing a delivery, passing on an offer, an offer timing out), the
    oldest waiting orders are offered first.
  - Retries also run oldest first.
- *Tests:* three new dispatch tests fail on the old code and pass on the new.

**2. Servers closed idle connections after 5 seconds.**
- *Before.* uvicorn and Next close a connection that has been idle for 5 s. A client that reuses it at that moment
  gets "server disconnected" (5 times in the run).
- *Why it matters.* Behind a load balancer this turns into intermittent 502s, because the load balancer keeps idle
  connections longer: our ALB keeps them 120 s.
- *Fix:* all five services keep idle connections 130 s: `--timeout-keep-alive 130` for core-api, realtime and worker,
  including the Railway start commands, and `--keepAliveTimeout 130000` for web and admin.

**3. The payment alert paged on ordinary declines.**
- *Before.* At 8% declines (normal for cards), a rush alone reached 3 failures in 15 minutes.
- *Fix:*
  - core_api now also reports `bhojango_payment_attempts_15m`.
  - `PaymentFailures` needs **3+ failures that are also 30%+ of payments**. An outage, where nearly every payment
    fails, still fires within one KPI refresh.
  - *Checked against the data:* replaying both runs' payments minute by minute, the old rule would have fired for
    35 and 9 minutes, and the new one for 0 in both. The worst ordinary 15-minute window was 18%.
  - `infra/observe/prometheus/alerts.test.yml` has promtool unit tests (the soak's own numbers don't fire it; a broken
    checkout does). They run in `make ci` (`ci-observe`).

## After the fixes: 60-minute re-run

Same scenario and order rate (75 orders in 60 minutes, the same rush shape), on a stack rebuilt with fixes 1 and 2.
The alert change (3) came after this run started, so it was checked by replaying the payment data and by the promtool
tests above.

| | 2-hour run (before) | 60-minute re-run (after) |
|---|---|---|
| Completion rate | 100% (130 of 130) | **100%** (70 of 70) |
| Waiting for a rider: median / p90 / **max** | 1.7 / 18.1 / **52.4 min** | 3.7 / 8.9 / **10.5 min** |
| Later orders served first (overtakes) | 646 | **14**. Some remain by design: a pass sends an order back to the queue, and an order goes to its nearest free rider, so one at another kitchen can go first |
| Delivery time: median / p90 / **max** | 12.1 / 28.5 / **61.5 min** | 13.5 / 19.5 / **21.6 min** |
| OrdersWithoutRider alert | 44 min | **6 min** |
| Dropped connections | 5 | **0** |
| Server errors, log error lines, WebSocket errors | 0, 0, 0 | 0, 0, 0 |
| Memory, Postgres and Redis connections | flat | flat (core-api +2%, realtime +5%, connections unchanged) |

The median wait rose a little: the same rider shortage is now shared evenly instead of falling on a few orders. The
long tail is gone.

## What it means for the pilot

- **Riders.** At the peak, orders arrived at about 2 a minute. Between them, the 8 riders delivered about
  **1.3 a minute**, even with travel shortened, so a backlog built for about 40 minutes. The tracker's 20–30 riders
  (task 38) cover it. With fewer riders on a given night, ops can:
  - add prep time for busy kitchens (busy mode);
  - pause a zone in admin;
  - watch the **OrdersWithoutRider** alert. It's the right signal, and the dispatch map shows who is free.
- **Problem reports in Boise mostly become tickets.** The automatic refund limit is $5 per order, below most single
  items ($9–22). That's 4 of 5 in this run; in Hyderabad (₹100) most would be refunded at once. Whether to raise it is
  Srini's call: it's the `auto_refund_limit` business rule, changeable in admin.
- **Nothing else needs changing before the pilot.** Memory, connections and Redis stay flat over two hours, nothing
  errors, and the monitoring catches the one real problem.
