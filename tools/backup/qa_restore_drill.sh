#!/bin/bash
# Restore drill from QA (R21), on a GitHub runner (.github/workflows/restore-drill.yml):
#   1. back up QA's database: pg_dump inside QA's own Postgres container, streamed out over
#      `railway ssh` (read-only: nothing on QA changes, no port is opened, no service is added)
#   2. restore it into a throwaway Postgres on this runner (PSQL_URL), nothing else in it
#   3. check it: migrations at head and matching the models, every table's row count against
#      QA's, the API's health checks on the restored data, and the finance invariants
#      (core_api/integration/test_finance_invariants.py: every payout run agrees with Reconciliation)
#   4. print how long each step took (RTO) and how old the newest restorable data is (RPO)
# Needs: RAILWAY_TOKEN (the QA project token), PSQL_URL / DATABASE_URL / REDIS_URL for the
# throwaway database, uv, the Railway CLI. The dump never leaves this runner: it isn't
# printed or uploaded (the logs of this public repo are public); only sizes, times and
# per-table row counts are.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${RUNNER_TEMP:-/tmp}/qa-drill"
rm -rf "$WORK"; mkdir -p "$WORK"; chmod 700 "$WORK"
RW="${RAILWAY_BIN:-railway}"
SVC="${PG_SERVICE:-postgres}"
fail() { echo "::error::DRILL FAILED: $*"; exit 1; }
now() { date +%s; }
t_all=$(now)
step() { echo; echo "== $(date -u +%H:%M:%S) $*"; }

# Guard: the restore target must be this runner's own database.
case "$PSQL_URL" in *@localhost:*|*@127.0.0.1:*) ;; *) fail "PSQL_URL must be a local throwaway database" ;; esac
case "$DATABASE_URL" in *@localhost:*|*@127.0.0.1:*) ;; *) fail "DATABASE_URL must be the local throwaway database" ;; esac
# pg_restore must be as new as QA's Postgres (16): the same image as the throwaway database.
PGIMG="${PG_IMAGE:-postgis/postgis:16-3.7}"
pgr() { docker run --rm --network host -v "$WORK:/w" "$PGIMG" pg_restore "$@"; }

# Where the backup comes from:
#   SOURCE_PSQL_URL set: a database on this runner built the way QA is (seed + demo seed): the
#     drill used while QA can't be read (see docs/launch/incident-plan.md, "Restore drill").
#   otherwise QA itself: one command run inside QA's Postgres container over `railway ssh`
#     (the service's own variables are there), sent base64-encoded so no quoting is lost.
#     Railway's CLI (4.x+) needs an SSH key registered on the Railway account for this.
SOURCE="${SOURCE_PSQL_URL:+seeded copy}"; SOURCE="${SOURCE:-QA}"
remote() {
  if [ -n "${SOURCE_PSQL_URL:-}" ]; then
    local u="${SOURCE_PSQL_URL#*://}"; local cred="${u%%@*}"; local hp="${u#*@}"; local db="${hp#*/}"; hp="${hp%%/*}"
    POSTGRES_USER="${cred%%:*}" POSTGRES_PASSWORD="${cred#*:}" POSTGRES_DB="$db" PGPORT="${hp#*:}"       docker run --rm -i --network host -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB -e PGPORT "$PGIMG" sh -c "$1"
  else
    timeout "${SSH_TIMEOUT:-900}" "$RW" ssh --service "$SVC" "echo $(printf '%s' "$1" | base64 -w0) | base64 -d | sh" </dev/null
  fi
}

COUNT_SQL='SELECT format($q$SELECT %L, count(*) FROM %I.%I$q$, table_schema || $q$.$q$ || table_name, table_schema, table_name)
FROM information_schema.tables
WHERE table_type = $q$BASE TABLE$q$ AND table_schema NOT IN ($q$pg_catalog$q$, $q$information_schema$q$, $q$tiger$q$, $q$tiger_data$q$, $q$topology$q$)
  AND NOT EXISTS (SELECT 1 FROM pg_depend d JOIN pg_class c ON c.oid = d.objid
                  WHERE d.deptype = $q$e$q$ AND c.relname = table_name AND c.relnamespace = table_schema::regnamespace)
ORDER BY 1 \gexec'
printf '%s\n' "$COUNT_SQL" > "$WORK/count.sql"   # every source counts the restored tables with it

if [ -n "${BACKUP_BUCKET:-}" ]; then
# R22: the newest hourly dump (tools/backup/hourly_dump.sh) from the backup bucket, with the read-only
# credentials in BACKUP_* (AWS CLI). Its checksum and its own row counts come with it.
SOURCE="the newest hourly dump in $BACKUP_BUCKET/${BACKUP_PREFIX:?}"
step "1. fetch the newest backup ($SOURCE)"
t0=$(now)
case "${BACKUP_ADDRESSING_STYLE:-}" in  # Railway buckets: "virtual-host" (see hourly_dump.sh)
  virtual*) aws configure set default.s3.addressing_style virtual ;;
  path) aws configure set default.s3.addressing_style path ;;
esac
s3() { AWS_ACCESS_KEY_ID="$BACKUP_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$BACKUP_SECRET_ACCESS_KEY" AWS_REGION="${BACKUP_REGION:-auto}"        aws --endpoint-url "$BACKUP_ENDPOINT_URL" s3 cp --only-show-errors "$@"; }
s3 "s3://$BACKUP_BUCKET/$BACKUP_PREFIX/latest.json" "$WORK/latest.json" || fail "no latest.json in the backup bucket"
key=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['key'])" "$WORK/latest.json")
taken=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['taken_at'])" "$WORK/latest.json")
s3 "s3://$BACKUP_BUCKET/$key" "$WORK/qa.dump" || fail "couldn't download $key"
s3 "s3://$BACKUP_BUCKET/$key.sha256" "$WORK/qa.sha256" || fail "no checksum for $key"
s3 "s3://$BACKUP_BUCKET/$key.counts" "$WORK/qa.counts.raw" || fail "no row counts for $key"
[ "$(sha256sum "$WORK/qa.dump" | cut -d' ' -f1)" = "$(tr -d ' 
' < "$WORK/qa.sha256")" ] || fail "checksum mismatch: $key"
grep -E '^[a-z_]+\.[a-z0-9_]+ [0-9]+$' "$WORK/qa.counts.raw" | sort > "$WORK/qa.counts"
qa_now=$(python3 -c "import sys,datetime as d; print(d.datetime.strptime(sys.argv[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=d.timezone.utc).isoformat())" "$taken")
age_min=$(python3 -c "import sys,datetime as d; t=d.datetime.strptime(sys.argv[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=d.timezone.utc); print(int((d.datetime.now(d.timezone.utc)-t).total_seconds()//60))" "$taken")
qa_bytes=$(stat -c %s "$WORK/qa.dump"); qa_rev=""
pgr --list /w/qa.dump > "$WORK/toc.txt" 2>/dev/null || fail "the dump isn't a readable pg_dump archive"
t_backup=$(( $(now) - t0 ))
echo "backup: $key, $(( qa_bytes / 1024 )) KB, $(grep -c 'TABLE DATA' "$WORK/toc.txt") tables of data, checksum OK, taken $qa_now ($age_min minutes ago), fetched in ${t_backup} s"
echo "$SOURCE: $(wc -l < "$WORK/qa.counts") tables, $(awk '{s+=$2} END {print s}' "$WORK/qa.counts") rows at dump time"
# RPO check: the hourly job must be running. Older than MAX_AGE_MINUTES (default 120) fails the drill.
[ "$age_min" -le "${MAX_AGE_MINUTES:-120}" ] || fail "the newest backup is $age_min minutes old: the hourly backup job has stopped"
else
step "1. back up ($SOURCE)"
t0=$(now)
# The newest row's time in QA, for RPO: what a backup taken now would hold.
remote 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qAt -c "SELECT now(), pg_database_size(current_database()), (SELECT version_num FROM alembic_version)"' \
  | tr -d '\r' | grep -E '^[0-9]{4}-' | tail -1 > "$WORK/qa-meta.txt" || fail "couldn't reach QA's Postgres over railway ssh"
[ -s "$WORK/qa-meta.txt" ] || fail "no answer from QA's Postgres (railway ssh)"
IFS='|' read -r qa_now qa_bytes qa_rev < "$WORK/qa-meta.txt"
echo "$SOURCE database: $(( qa_bytes / 1024 / 1024 )) MB on disk, migration $qa_rev, clock $qa_now"
# Row counts first, then the dump: QA's demo rider simulator may add rows in between (reported, not failed).
printf '%s\n' "$COUNT_SQL" > "$WORK/count.sql"
remote "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -h 127.0.0.1 -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -qAt -F ' ' <<'SQL'
$COUNT_SQL
SQL" | tr -d '\r' | grep -E '^[a-z_]+\.[a-z0-9_]+ [0-9]+$' | sort > "$WORK/qa.counts"
echo "$SOURCE: $(wc -l < "$WORK/qa.counts") tables, $(awk '{s+=$2} END {print s}' "$WORK/qa.counts") rows"
# Custom format (compressed), base64 between markers: the ssh session is a terminal, not a byte pipe.
remote 'echo __DUMP_BEGIN__; PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges | base64 -w 0; echo; echo __DUMP_END__' \
  > "$WORK/raw.txt" 2> "$WORK/ssh.err" || fail "pg_dump over railway ssh failed ($(tail -c 300 "$WORK/ssh.err" | tr -d '\n'))"
tr -d '\r' < "$WORK/raw.txt" | sed -n '/__DUMP_BEGIN__/,/__DUMP_END__/p' | grep -v '__DUMP_' | tr -d '\n ' | base64 -d > "$WORK/qa.dump" \
  || fail "the dump didn't decode (cut short?)"
rm -f "$WORK/raw.txt"
pgr --list /w/qa.dump > "$WORK/toc.txt" 2>/dev/null || fail "the dump isn't a readable pg_dump archive"
t_backup=$(( $(now) - t0 ))
echo "backup: $(( $(stat -c %s "$WORK/qa.dump") / 1024 )) KB, $(grep -c 'TABLE DATA' "$WORK/toc.txt") tables of data, sha256 $(sha256sum "$WORK/qa.dump" | cut -c1-16)…, ${t_backup} s"

fi

step "2. restore into the throwaway database"
t0=$(now)
left=$(psql "$PSQL_URL" -qAt -c "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")
[ "$left" = 0 ] || fail "the throwaway database isn't empty ($left tables)"
pgr --no-owner --no-privileges --exit-on-error -j 4 -d "$PSQL_URL" /w/qa.dump 2> "$WORK/restore.err" \
  || fail "pg_restore: $(tail -5 "$WORK/restore.err")"
t_restore=$(( $(now) - t0 ))
echo "restored in ${t_restore} s"

step "3a. migrations: at head, and the models match"
t0=$(now)
cd "$ROOT/backend"
rev=$(psql "$PSQL_URL" -qAt -c "SELECT version_num FROM alembic_version")
head=$(uv run --frozen alembic heads 2>/dev/null | awk '{print $1}')
echo "restored: $rev; this code's head: $head"
[ -z "$qa_rev" ] || [ "$rev" = "$qa_rev" ] || fail "restored migration $rev isn't QA's $qa_rev"
[ "$rev" = "$head" ] || echo "::warning::QA is at $rev, this branch's head is $head (QA deploys dev; a newer branch is ahead)"
[ "$rev" = "$head" ] && { uv run --frozen alembic check || fail "alembic check on the restored data"; }

step "3b. every table's row count against QA's"
psql "$PSQL_URL" -qAt -F ' ' -f "$WORK/count.sql" | sort > "$WORK/restored.counts"
echo "restored: $(wc -l < "$WORK/restored.counts") tables, $(awk '{s+=$2} END {print s}' "$WORK/restored.counts") rows"
diffs=$(join -a1 -a2 -e MISSING -o 0,1.2,2.2 "$WORK/qa.counts" "$WORK/restored.counts" | awk '$2 != $3')
if [ -z "$diffs" ]; then echo "every table matches"
else
  echo "tables that differ (QA counted before the dump; the demo simulator keeps adding rows):"
  echo "$diffs" | sed 's/^/  /'
  # Fewer rows than QA had BEFORE the dump would mean data was lost; more is QA moving on.
  lost=$(echo "$diffs" | awk '$2 == "MISSING" || $3 == "MISSING" || $3 < $2')
  [ -z "$lost" ] || fail "rows missing after the restore: $lost"
fi

step "3c. the API on the restored data: /health and /health/ready"
APP_ENV=test JWT_DEV_KEY_PATH="$WORK/jwt-dev.pem" uv run --frozen uvicorn core_api.main:app --port 8001 > "$WORK/api.log" 2>&1 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
ok=0
for _ in $(seq 1 60); do curl -sf -m 3 localhost:8001/health/ready > "$WORK/ready.json" 2>/dev/null && { ok=1; break; }; sleep 2; done
[ "$ok" = 1 ] || { tail -20 "$WORK/api.log"; fail "the API isn't ready on the restored data"; }
curl -sf -m 5 localhost:8001/health; echo
cat "$WORK/ready.json"; echo
# A read that touches the restored data: the public markets directory.
curl -sf -m 10 localhost:8001/api/v1/markets/directory | python3 -c "import json,sys; d=json.load(sys.stdin); print('markets directory on the restored data:', d['totals'])"   || fail "the markets directory didn't load from the restored data"
kill $API 2>/dev/null; wait $API 2>/dev/null; trap - EXIT

step "3d. finance invariants on the restored data (payout runs agree with Reconciliation, last 4 weeks)"
RUN_MIGRATED_DB_TESTS=1 uv run --frozen pytest core_api/integration/test_finance_invariants.py -q --tb=short -p no:cacheprovider \
  || fail "finance invariants on QA's data"
t_verify=$(( $(now) - t0 ))

step "4. RTO and RPO"
total=$(( $(now) - t_all ))
echo "backup ${t_backup} s · restore ${t_restore} s · checks ${t_verify} s · whole drill ${total} s"
if [ -n "${age_min:-}" ]; then
  echo "source: $SOURCE. RPO of this drill: $age_min minutes (the newest hourly copy, taken $qa_now; at most 60 while the job runs)."
else
  echo "source: $SOURCE. RPO of this drill: 0 (a backup taken now, at $qa_now)."
fi
{
  echo "### Restore drill (source: $SOURCE)"
  echo "| Step | Time |"; echo "|---|---|"
  echo "| Back up ($SOURCE, $(( qa_bytes / 1024 / 1024 )) MB database) | ${t_backup} s |"
  echo "| Restore into a throwaway database | ${t_restore} s |"
  echo "| Checks (migrations, row counts, health, finance invariants) | ${t_verify} s |"
  echo "| **Whole drill** | **${total} s** |"
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
rm -rf "$WORK"
echo "DRILL PASSED in ${total} s"
