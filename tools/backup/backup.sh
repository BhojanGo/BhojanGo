#!/bin/sh
# Back up the Compose stack's Postgres database (logical, pg_dump custom format).
#   tools/backup/backup.sh [out-dir]          # default: ./backups
# Uses COMPOSE_PROJECT_NAME (default bhojango) and COMPOSE_FILES (default the dev stack).
# Writes bhojango-<UTC timestamp>.dump, its sha256, and a row count per table
# (<dump>.counts) to check a restore against. See docs/runbooks/backup-restore.md.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
OUT="${1:-$ROOT/backups}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose ${COMPOSE_FILES:--f $ROOT/infra/docker/compose.yaml}"
mkdir -p "$OUT"
NAME="bhojango-$(date -u +%Y%m%dT%H%M%SZ).dump"

$COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -Z 6 -f /tmp/backup.dump && cat /tmp/backup.dump && rm /tmp/backup.dump' > "$OUT/$NAME"
[ -s "$OUT/$NAME" ] || { echo "backup failed: empty dump" >&2; exit 1; }
(cd "$OUT" && sha256sum "$NAME" > "$NAME.sha256")  # by file name, so it checks wherever the dump is copied
sh "$ROOT/tools/backup/counts.sh" > "$OUT/$NAME.counts"
echo "$OUT/$NAME ($(wc -c < "$OUT/$NAME") bytes, $(wc -l < "$OUT/$NAME.counts") tables)"
