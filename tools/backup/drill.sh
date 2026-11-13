#!/bin/sh
# Backup drill on a throwaway stack (Compose project bhojango-drill; your dev
# stack is not touched):
#   1. start the backend, seed, run G1 so there are real orders, payments, payouts
#   2. back up (pg_dump) and count every table
#   3. wipe: delete the Postgres container AND its volume (the disk is gone)
#   4. restore into a fresh database; row counts must match; migrations at head
#   5. start the services on the restored data and run G1 again: it must pass
#   tools/backup/drill.sh        (about 10 minutes; see docs/runbooks/backup-restore.md)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME=bhojango-drill MSYS_NO_PATHCONV=1
export COMPOSE_FILES="-f $ROOT/infra/docker/compose.yaml -f $ROOT/infra/docker/e2e.compose.yaml"
COMPOSE="docker compose $COMPOSE_FILES"
OUT="$ROOT/backups/drill"
mkdir -p "$ROOT/backups"
step() { echo; echo "== $(date -u +%H:%M:%S) $*"; }
fail() { echo "DRILL FAILED: $*" >&2; $COMPOSE --profile e2e --profile backend down -v --remove-orphans >/dev/null 2>&1; exit 1; }
start=$(date +%s)

step "1. start the backend, seed, run G1"
$COMPOSE --profile backend up -d --build --wait >/dev/null 2>&1 || fail "stack didn't start"
$COMPOSE exec -T core-api python /srv/tools/seed/seed.py >/dev/null || fail "seed"
$COMPOSE --profile e2e run --rm --build g1 > "$OUT.g1-before.log" 2>&1 || fail "G1 before the backup (see $OUT.g1-before.log)"
grep -E "passed|failed" "$OUT.g1-before.log" | tail -1

step "2. back up"
rm -rf "$OUT"; mkdir -p "$OUT"
DUMP=$(sh "$ROOT/tools/backup/backup.sh" "$OUT" | tail -1) || fail "backup"
echo "$DUMP"
DUMP=$(ls "$OUT"/*.dump)
head -3 "$DUMP.counts"; echo "  ... $(awk '{s+=$2} END {print s}' "$DUMP.counts") rows in all"

step "3. wipe: stop the services, delete Postgres and its volume"
$COMPOSE --profile backend stop core-api realtime worker >/dev/null 2>&1
$COMPOSE rm -sf postgres >/dev/null 2>&1
docker volume rm "${COMPOSE_PROJECT_NAME}_postgres_data" >/dev/null || fail "volume not removed"
$COMPOSE up -d --wait postgres >/dev/null 2>&1 || fail "fresh Postgres"
left=$(sh "$ROOT/tools/backup/counts.sh" | awk '$2 > 0' | wc -l)
echo "fresh database: $left tables with rows (expect 0)"
[ "$left" -eq 0 ] || fail "the wipe left data behind"

step "4. restore"
t0=$(date +%s)
sh "$ROOT/tools/backup/restore.sh" "$DUMP" || fail "restore"
echo "restore took $(( $(date +%s) - t0 )) s"
rev=$($COMPOSE exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qAt -c "SELECT version_num FROM alembic_version"')
echo "alembic revision: $rev"

step "5. services on the restored data; G1 must pass"
$COMPOSE --profile backend up -d --wait >/dev/null 2>&1 || fail "services on the restored database"
$COMPOSE --profile e2e run --rm g1 > "$OUT.g1-after.log" 2>&1 || fail "G1 after the restore (see $OUT.g1-after.log)"
grep -E "passed|failed" "$OUT.g1-after.log" | tail -1

$COMPOSE --profile e2e --profile backend down -v --remove-orphans >/dev/null 2>&1
echo; echo "DRILL PASSED in $(( $(date +%s) - start )) s (dump: $DUMP)"
