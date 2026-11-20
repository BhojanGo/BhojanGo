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

Two kinds of backup (R22), in production and in QA:

| | What | When, kept | Restores to | Use it for |
|---|---|---|---|---|
| **Volume backups** | Railway's snapshots of the `postgres-data` volume | daily (kept 6 days) and weekly (kept 27 days), plus a manual one before every release with migrations ([go-live.md](go-live.md) step 3) | **the same volume only, in place** (Railway can't restore a volume backup anywhere else) | the whole volume lost or corrupt |
| **Hourly dumps** | `pg_dump` by the cron service `db-backup` ([hourly_dump.sh](../../tools/backup/hourly_dump.sh)) into its own private bucket `db-backups`, with a checksum and row counts | every hour at :07, kept 7 days | **any** Postgres 16 (a new service, a throwaway database, a laptop) | a bad migration or bulk action found hours later; reading the lost window; the weekly restore test |

[backup-restore.md](../runbooks/backup-restore.md) still describes the earlier AWS (RDS) setup; this section supersedes
it for Railway.

### Steps

1. **Stop new writes.** Admin → Incidents → pause ordering everywhere, with the reason. Tell customers and partners
   (templates above).
2. **Keep what is there.** Railway → `postgres` → Backups → *Create backup* of the damaged volume first, so the
   restore can be undone and the lost window can be read later.
3. **Pick the restore point:** the newest backup from before the damage (for a bad release, its pre-release backup).
4. **Restore**, either way, then restart `core-api`, `realtime` and `worker` once Postgres is up:
   - **From a volume backup:** Railway → `postgres` → Backups → that backup → *Restore*, then deploy the staged
     change.
   - **From an hourly dump** (finer: the hour before the damage): download it from the `db-backups` bucket
     (`<env>/YYYY/MM/DD/bhojango-<time>.dump`, check its `.sha256`), then
     `pg_restore --clean --if-exists --no-owner -j 4 -d <DATABASE_URL> bhojango-<time>.dump` (or restore into a new
     database first, check it, and point `DATABASE_URL` at it).
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

That drill's source was a copy built the way QA is, because QA had no backups then.

### Backups on QA and the weekly restore test (R22, deployed on QA in R23)

- **QA's volume backups are on** (2026-11-20, Srini's approval): daily at 20:23 UTC, kept 6 days, and weekly on
  Saturdays at 00:57 UTC, kept 27 days. The project is on Railway's Pro plan already, so no upgrade was needed;
  the storage is billed with the volume (cents a month at QA's size). Railway restores a volume backup only over the
  live volume, so it is not drilled on QA: that would overwrite QA. Production rehearses it once before launch
  (go-live step 3).
- **The hourly dump is built and tested.** In CI on every change to the backup code, `restore-drill.yml`
  (`backup-job`) builds the `db-backup` image and runs it against a database built like QA and a local S3 server.
  It checks that the job dumps, uploads, writes `latest.json`, prunes a dump over 7 days old, and that the drill
  restores what it wrote. **It runs on QA since 2026-11-20** (R23, below).
- **The weekly restore test:** every Monday at 07:17 UTC, `restore-drill.yml` takes the newest dump from the bucket
  (read with the bucket's credentials, kept as GitHub secrets `BACKUP_*`), checks its sha256, restores it into a
  throwaway database on the runner and checks it (migrations, every table's row count against the dump's own,
  health, finance invariants). It **fails if the newest dump is over 2 hours old**, so a stopped backup job shows
  up as a red run.

**On QA (R23, 2026-11-20, Srini's approval):** the `db-backups` bucket (`sjc`, private) and the `db-backup` cron
service (hourly at :07, 0.5 vCPU / 0.5 GB, restart never) are created as `.railway/railway.ts` defines them, with the
bucket's keys as sealed variables and in the GitHub secrets `BACKUP_*` (never printed). The project token can't
create buckets; the workspace token did. The first copy ran at 22:09 UTC: `qa/2026/11/20/bhojango-20261120T220905Z.dump`,
1,362 KB, 58 tables, 10,593 rows, 12 s.

**Restore drill on QA's real copy** (run [44827699088](https://github.com/BhojanGo/BhojanGo/actions/runs/44827699088),
`source: bucket`, the same job the weekly schedule runs; QA itself only read):

| Step | Result | Time |
|---|---|---|
| Fetch `latest.json` and the dump, check its sha256 | OK; the copy was 9 minutes old (RPO of this drill) | 11 s |
| Restore into a throwaway database | OK | 1 s |
| Migrations at head, models match | OK | 3 s |
| Row counts against the dump's own | 57 tables, 10,593 rows, all equal | — |
| `/health` and `/health/ready` on the restored data | healthy (database, redis); markets directory 2 countries, 42 kitchens | 4 s |
| Finance invariants (payout runs agree with Reconciliation, last 4 weeks) | passed | 3 s |
| **Whole drill** | **passed** | **22 s** |

**Cost:** Railway buckets are $0.015 per GB-month, with free egress and free API calls. QA's dumps: an estimated 1–5 MB each
(the seeded copy's was 0.8 MB) × 24 a day × 7 days ≈ 0.2–0.8 GB ≈ **$0.003–0.013 a month**. Production at launch is similar. The cron service runs
about a minute an hour (well under $1 a month). Cloudflare R2's free tier (10 GB) would also cost $0, but it
needs a Cloudflare account and its keys. Its one advantage is a second provider, so a Railway account problem
couldn't take both the database and its backups. That's worth doing after launch.

### RPO and RTO

| | RPO (data that can be lost) | RTO (time to be back) |
|---|---|---|
| QA (from 2026-11-20) | **1 hour** (the hourly dump; the volume backups, daily and weekly, are the second copy) | Volume restore: minutes. Dump: about the same as production. QA can also be reseeded in about 5 minutes |
| Production as planned | **1 hour** (the hourly dump; the volume backups are the second copy) | **About 30 minutes**: the restore itself takes seconds to a minute at our size (the drill restored 23 MB in 1 s; QA's whole volume is 185 MB), plus deciding, restarting and checking |

Payments taken in the lost window are still in Stripe (step 6).

## Still to build (not in round 17)

1. Messages to kitchens and delivery partners in bulk (customers only today).
2. A credit to customers' BhojanGo balance in bulk (refunds go back to how they paid).
3. A text message (SMS) channel for bulk messages (push and email today).
