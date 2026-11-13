#!/bin/sh
# Restore a dump made by backup.sh into the stack's Postgres (the database must
# exist; a fresh container creates it). Checks the sha256 first and the row
# counts after.
#   tools/backup/restore.sh backups/bhojango-20261112T230000Z.dump
set -eu
DUMP="${1:?usage: restore.sh <dump>}"
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose ${COMPOSE_FILES:--f $ROOT/infra/docker/compose.yaml}"

if [ -f "$DUMP.sha256" ]; then
  (cd "$(dirname "$DUMP")" && sha256sum -c "$(basename "$DUMP").sha256" >/dev/null) || { echo "checksum mismatch: $DUMP" >&2; exit 1; }
fi
$COMPOSE exec -T postgres sh -c 'cat > /tmp/restore.dump' < "$DUMP"
# --clean --if-exists: drop what's there first; --no-owner: the target's own role owns it all.
$COMPOSE exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error -j 4 /tmp/restore.dump && rm /tmp/restore.dump'
if [ -f "$DUMP.counts" ]; then
  sh "$ROOT/tools/backup/counts.sh" > /tmp/restored.counts
  if diff -u "$DUMP.counts" /tmp/restored.counts >/dev/null; then
    echo "restored: $(wc -l < "$DUMP.counts") tables, every row count matches"
  else
    echo "row counts differ after restore:" >&2; diff -u "$DUMP.counts" /tmp/restored.counts >&2 || true; exit 1
  fi
fi
