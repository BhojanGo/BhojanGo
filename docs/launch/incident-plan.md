# Incident plan (draft)

For Boise's launch. What to do when orders can't be placed, paid, cooked or delivered, or when money or data is
at risk. Draft for Srini to approve; names and phone numbers are filled in before launch.

The tools are in admin → **Incidents** (round 17). Every action there needs the right role, a reason and a
confirmation step, and is written to the audit log (the **Log** at the bottom of the page).

## Who is called

| Role | Who | When |
|---|---|---|
| Incident lead (decides, talks to customers and partners) | Srini | Every incident |
| Engineering (finds the cause, pauses, fixes, refunds) | Claude Code session started by Srini; later an on-call engineer | Every incident |
| Payments (Stripe disputes, payouts) | Srini, with Stripe support | Anything with money |
| Kitchens and delivery partners | Srini (support line) | When they are affected |

Alerts (PaymentFailures, API errors, webhooks failing, no orders in a dinner hour) page the incident lead once
monitoring is set up (readiness item 14). Severity: **1** nobody can order or pay → act at once; **2** one zone, kitchen
or payment method broken → within 30 minutes; **3** degraded (slow, a feature missing) → same day.

## First 15 minutes

1. Say it out loud: post in the incident channel what is broken, since when, and who leads.
2. Stop new damage: pause what is failing (below), so customers can't place orders that will fail.
3. Look at what was already caught: orders placed but not accepted, paid but not delivered (Operations).
4. Tell the people affected (Incidents → Message customers; the templates below).
5. Fix or roll back (Railway: redeploy the last good build); then resume, watching the first orders.
6. Refund what went wrong (Incidents → Bulk refund), and tell those customers.
7. Within two days: a short write-up (what happened, the cause, the fix) and a PLAYBOOK lesson if it cost more than an hour.

## Pausing

New orders stop; **orders already placed carry on** (they can still be paid, cooked and delivered).

| What | Where in admin | Who |
|---|---|---|
| **Everywhere** | Incidents → Pause ordering → Where: Everywhere | Super admin |
| **A country** | Incidents → Pause ordering → Where: This country (country in the scope bar) | Country manager |
| **A city** | Incidents → Pause ordering → Where: This city (city in the scope bar) | Country manager, city ops |
| **A zone** | Markets → country → city → the zone → "Pause this zone…" (a reason and an end time) | Country manager, city ops |
| **A kitchen** | Incidents → Pause a kitchen: find it, optional "Back at" time | Country manager, city ops |
| **An offer or fee rule** | Pricing & Rules → the rule → Pause (kitchen offers) or End now | Rule editors |

- An ordering pause has an optional **note for customers** ("Back by 9 pm") and an optional end time. The website
  and the customer app show "Ordering in {area} is paused for now while we fix a problem. Orders already on their
  way will still arrive." in the customer's language, plus the note as written. The reason stays with admins.
- While ordering is paused, the bag on the website and in the app says "Ordering is paused" (or "This kitchen is
  closed for now") and its checkout button is disabled with the same words.
- A paused kitchen shows **"Closed for now"** to customers (and "Back around {time}" when a time is set); its menu
  can be read but not ordered from. The kitchen can't undo it from its tablet; it reopens at the "Back at" time
  or when an admin resumes it.
- Resume from the same place: "Resume ordering" / "Resume", with a reason.

## Refunds

| What | Where | Who |
|---|---|---|
| One order, by item or in full | Operations → the order → Refund (reason, who is at fault) | Support (up to its limit), city ops, country manager, finance |
| Orders that fail in a pause | Orders not accepted in time are cancelled and refunded in full automatically | Automatic |
| **Many orders at once** | Incidents → Bulk refund: a kitchen, a zone or the whole city, a time window (7 days at most), in full or a percentage → Preview (each order, the count and the total) → reason → confirm | City ops, country manager, finance |

- A bulk refund goes through the payment provider order by order (Stripe in test mode on QA); one failure doesn't
  stop the others, and the list shows how many failed.
- **Above the city's automatic refund limit** (business rule "Automatic refunds for problem reports", per order) a
  **second admin** (country manager or finance, not the one who asked) approves it from the same list first.
- BhojanGo pays bulk refunds: kitchens' payouts don't change (a kitchen's own mistake is refunded by item instead).

## Customer messages (templates)

Incidents → **Message customers**: to the customers of a bulk refund (one message per refunded order, with its
kitchen and amount) or to everyone who ordered in a city in the last day, 7 or 30 days (the city is picked from
the cities you look after; {area} in a message is that city's name from Markets, never typed). Push and email, each
customer in their own language (8 languages; texts in `backend/shared/texts.py` `INCIDENT_MESSAGES`). Preview first:
how many people, and the message in English. **Outside production only test accounts get it** (the seed's
`@example.com` addresses and test phone numbers); the preview says how many others were left out.

| Message | Placeholders | Audience |
|---|---|---|
| **Order can't be completed:** "We're sorry: {restaurant} can't finish your order {code}. We've cancelled it and refunded {amount} to how you paid; it usually shows in 3–5 working days." | from each order | A bulk refund's customers |
| **Refund sent:** "We're sorry about your order {code} from {restaurant}. We've refunded {amount} to how you paid; it usually shows in 3–5 working days." | from each order | A bulk refund's customers |
| **Delay:** "Your order is running late because of a problem on our side. It should arrive by {time}. We're sorry for the wait." | {time}: typed by the admin | Either |
| **Ordering paused:** "Ordering in {area} is paused for now while we fix a problem. Orders already on their way will still arrive. We'll let you know when we're back." | {area}: the recipients' city | Either |
| **We're back:** "Ordering in {area} is open again. Thank you for waiting." | {area}: the recipients' city | Either |
| **Payment problem:** "Your payment didn't go through because of a problem with our payment provider, not your card. You haven't been charged. Please try again in a few minutes." | none | Either |

Kitchens and delivery partners (support line or the partner apps, one at a time for now):

- **Kitchen partners:** "Ordering is paused in {area} from {time} because of {reason}. Orders already accepted still count and will be paid in your weekly payout."
- **Delivery partners:** "Offers are paused in {area} from {time}. Trips already accepted will be paid as usual, including the minimum pay for your time online."

## Database restore

When to restore: data is lost or wrong in many places (a bad migration, a bad bulk action, the volume is gone). For a
few wrong rows, fix them instead. A restore throws away everything written after the backup.

Production is Postgres on Railway (service `postgres`, volume `postgres-data`), backed up by Railway's volume backups:
daily, keep 7, plus a manual backup before every release with migrations ([go-live.md](go-live.md) step 3).
[backup-restore.md](../runbooks/backup-restore.md) still describes the earlier AWS (RDS) setup; this section supersedes
it for Railway.

### Steps

1. **Stop new writes.** Admin → Incidents → pause ordering everywhere, with the reason. Tell customers and partners
   (templates above).
2. **Keep what is there.** Railway → `postgres` → Backups → *Create backup* of the damaged volume first, so the
   restore can be undone and the lost window can be read later.
3. **Pick the restore point:** the newest backup from before the damage (for a bad release, its pre-release backup).
4. **Restore:** Railway → `postgres` → Backups → that backup → *Restore*, then deploy the staged change. Restart
   `core-api`, `realtime` and `worker` once Postgres is up.
5. **Check before reopening** (what the drill checks; the commands are in `tools/backup/qa_restore_drill.sh`):
   - migrations: `alembic current` is the release's head, and `alembic check` finds no differences;
   - row counts per table look right (none empty that shouldn't be; orders up to the restore point);
   - `GET /health/ready` on core-api, realtime and worker (the same checks as `tools/railway/qa-job.sh checks`);
   - the finance invariants: `RUN_MIGRATED_DB_TESTS=1 pytest core_api/integration/test_finance_invariants.py`
     (every payout run agrees with Reconciliation; it changes nothing).
6. **The lost window.** Orders, sign-ups and kitchen edits after the restore point are gone. Stripe still has every
   payment taken in that window: list them in Stripe (payments since the restore point), refund the ones whose orders
   no longer exist, and message those customers. If a payout run was paid in the window, its transfers are in
   Stripe Connect but not in Finance: check the next run against those transfers before approving it, so nobody is
   paid twice.
7. **Resume** ordering, watch the first orders, then write the incident up (First 15 minutes, step 7).

### Restore drill (2026-11-20, round 21)

`.github/workflows/restore-drill.yml` runs `tools/backup/qa_restore_drill.sh` on a GitHub runner: back up, restore
into an empty throwaway database, check. Nothing is written anywhere but the runner, and the dump is never printed or
uploaded.

| Step | Time |
|---|---|
| Back up (pg_dump, custom format: 796 KB, 57 tables) | 1 s |
| Restore into an empty database (`pg_restore -j 4`) | 1 s |
| Checks: migrations at head and `alembic check` clean; all 56 tables' row counts equal (4,519 rows); core-api `/health` and `/health/ready` healthy on the restored data, the markets directory loads (2 countries, 42 kitchens); finance invariants pass | 10 s |
| **Whole drill** | **12 s** (run [44672472054](https://github.com/BhojanGo/BhojanGo/actions/runs/44672472054)) |

**The source was a copy built the way QA is** (migrations, the seed and the demo seed: 23 MB), **not QA's own data**,
because QA can't be read without a change Srini has to approve:

- **QA has no backups.** Railway lists no backups and no backup schedule for QA's `postgres-data` volume (checked
  2026-11-20; [boise-readiness.md](boise-readiness.md) item 15 said "Ready on QA", which was wrong).
- **QA's Postgres is private**, with no TCP proxy. `railway ssh` (the drill's `source: qa` mode uses it) needs an SSH
  key registered on the Railway account (Railway CLI 4.x and later); the older keyless CLI can't run a command.

Any one of these makes the drill run on QA's own data; each needs Srini's approval:

| Option | What changes | Cost |
|---|---|---|
| A. Turn on QA's volume backups (daily, keep 7), then restore the newest into a temporary service | QA's settings; a temporary service in QA | Backup storage (QA's volume is under 200 MB: cents a month) |
| B. Register an SSH key on the Railway account for drills, kept as a GitHub secret | The Railway account; nothing on QA | Free |
| C. A temporary `qa-runner` service in QA dumps the database to the runner (as the payments e2e already does) | A temporary service in QA, deleted after | Free |

Recommendation: **A**. It rehearses go-live step 3, and QA should have backups anyway. Then run the drill with
`source: qa`.

### RPO and RTO

| | RPO (data that can be lost) | RTO (time to be back) |
|---|---|---|
| QA today | **Everything**: no backups. QA is demo data and can be reseeded, so this is acceptable for QA only | Reseed: about 5 minutes |
| Production as planned (daily backups) | **Up to 24 hours** of orders, sign-ups and kitchen edits (payments in that window are still in Stripe, step 6) | **About 30 minutes**: the restore itself takes seconds to a minute at our size (the drill restored 23 MB in 1 s; QA's whole volume is 185 MB), plus deciding, restarting and checking |
| Production, recommended | **1 hour**: add an hourly `pg_dump` to the uploads bucket from a worker job (Railway volume backups have no point-in-time restore) | The same |

The hourly dump is a small change (a worker job, and a bucket prefix that keeps 7 days). It is in
[STATUS.md](../STATUS.md) for Srini to decide.

## Still to build (not in round 17)

1. Messages to kitchens and delivery partners in bulk (customers only today).
2. A credit to customers' BhojanGo balance in bulk (refunds go back to how they paid).
3. A text message (SMS) channel for bulk messages (push and email today).
