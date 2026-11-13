# Backup and restore

Postgres holds everything that matters: orders, payments and refunds, payouts, menus, rules, accounts and the audit
log. This runbook covers how it is backed up, how to restore it, and the drill that proves a restore works.

## Drill: done 2026-11-12, passed

```sh
tools/backup/drill.sh        # ~2 minutes; a throwaway stack (Compose project bhojango-drill), dev data untouched
```

| Step | Result |
|---|---|
| 1. Start the backend, seed, run G1 (an order from payment to payouts and messages, India and the US) | 2 passed |
| 2. Back up with `pg_dump -Fc`, plus a sha256 and an exact row count for every table | 41 tables (128 KB) |
| 3. Wipe: stop the services, delete the Postgres container **and its volume** | Fresh database: 0 tables with rows |
| 4. Restore with `pg_restore --clean --no-owner`; check the checksum and compare the row counts | Every count matches, in 2 s; migrations at head (`0021_ops_alerts`) |
| 5. Start the services on the restored data; run G1 again | 2 passed |

Run the drill again after any change to the schema, the backup scripts or the Postgres version, and in any case
**every quarter**. Record the date and result here.

## The scripts (`tools/backup/`)

| Script | What it does |
|---|---|
| `backup.sh [dir]` | `pg_dump` (custom format, compressed) of the stack's database to `backups/bhojango-<UTC time>.dump`, plus `.sha256` and `.counts` (rows per table) |
| `restore.sh <dump>` | Checks the sha256, restores into the stack's database (`--clean --if-exists --no-owner`), then compares the row counts with the backup's |
| `counts.sh` | Exact row count of every table; tables owned by extensions (PostGIS `spatial_ref_sys`) are left out |
| `drill.sh` | Steps 1–5 above, on a throwaway stack |

They act on `COMPOSE_PROJECT_NAME` (default `bhojango`, the `make dev` stack). Dumps go in `backups/`, which git
ignores. **Never commit a dump: it holds customers' personal data.**

## Production (AWS, when deployed)

The Terraform (`infra/terraform/modules/rds`) already sets:

| Setting | Staging | Prod |
|---|---|---|
| Automated backups with point-in-time restore | 3 days | **14 days** |
| Backup window | 03:00–04:00 UTC | 03:00–04:00 UTC (≈ 8:30 am IST, 9–10 pm Boise: before the lunch rush, after Boise's dinner) |
| Multi-AZ standby | no | **yes** |
| Deletion protection; final snapshot on delete | no | **yes** |

Targets: **RPO 5 minutes** (point-in-time restore) and **RTO 1 hour** (a new instance from a snapshot, then repoint
the services).

### Restore in production

1. **Stop writes.** Scale `core-api`, `realtime` and `worker` to 0 (or pause the city zones in admin, if only some
   data is wrong).
2. **Pick the moment.** Choose the time just before the incident (from the audit log or the alerts).
3. **Restore beside the old database, never over it.** RDS → *Restore to point in time* → a new instance,
   `bhojango-prod-restore-<date>`, in the same subnet group and security group. Or *Restore snapshot* for a manual
   snapshot.
4. **Check it.**
   - Connect from a bastion task.
   - `SELECT version_num FROM alembic_version` must be the deployed release's head.
   - Run `tools/backup/counts.sh` against it (or the same query) and compare with the old instance.
   - Spot-check the latest orders.
5. **Switch.** Update the `DATABASE_URL` secret to the new endpoint, then scale the services back up. core_api runs
   `alembic upgrade head` on start; it's a no-op if already at head.
6. **Verify.** Watch Grafana / the admin overview for 15 minutes (orders, payments, no error spike). Place a test
   order in each live city.
7. **Clean up.** Keep the old instance for 7 days (renamed `…-old`), then delete it with a final snapshot.
8. **Reconcile.** Run Finance → Reconciliation for the affected days. Payments captured in the gap exist at the
   payment provider but not in our database; the provider's webhooks are replayed or matched by hand.

### Before every release with migrations

Take a manual snapshot `pre-<release>` (RDS → *Take snapshot*). If the migration goes wrong, restore from it (step 3
onwards).

## What isn't in Postgres

| Data | Where | If lost |
|---|---|---|
| Redis (sessions, OTP codes, dispatch state, riders' last positions, caches) | ElastiCache / the redis container | Rebuilt as people use the apps. Riders go online again; codes are re-sent. Nothing to restore. |
| Uploaded files (delivery photos, documents, problem photos) | S3 (`bhojango-uploads`) | Turn on S3 versioning in prod (one setting, cents per month). Locally they're in LocalStack and not backed up. |
| JWT signing key, provider keys | Secrets Manager (prod); a volume (`jwt_keys`) locally | Losing the signing key signs everyone out; nothing else. |
| Monitoring data (Prometheus, Loki, Tempo) | `make observe` volumes, 3 days | Not backed up; it's diagnostic. |

## On call

Alerts reach the admin console and the logs (`docs/runbooks/observe.md`). Before the pilot, name a primary and a
backup for each week in the team calendar, with one rule: whoever is on call can run this runbook. Who is on call is
the team's decision, not part of the code.
