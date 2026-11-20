#!/bin/sh
# Hourly logical backup (R22): pg_dump of the environment's database to object storage, kept KEEP_DAYS.
# Runs as the Railway cron service `db-backup` (infra/railway/db-backup.Dockerfile, .railway/railway.ts):
# Railway starts it every hour, it backs up, prunes, and exits.
#
#   s3://$BACKUP_BUCKET/$BACKUP_PREFIX/YYYY/MM/DD/bhojango-YYYYMMDDTHHMMSSZ.dump      pg_dump -Fc (compressed)
#                                                              .dump.sha256  its checksum
#                                                              .dump.counts  rows per table at dump time
#   s3://$BACKUP_BUCKET/$BACKUP_PREFIX/latest.json             the newest dump's key, size, sha256, time
#
# Reads the database only (pg_dump takes a consistent snapshot; no locks beyond AccessShare).
# Needs: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE, BACKUP_BUCKET BACKUP_PREFIX, AWS_ENDPOINT_URL
# AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_REGION; optional KEEP_DAYS (default 7).
# Prints sizes, counts and keys only: never a credential or a row.
set -eu
: "${BACKUP_BUCKET:?}" "${BACKUP_PREFIX:?}" "${AWS_ENDPOINT_URL:?}" "${PGHOST:?}" "${PGDATABASE:?}"
KEEP_DAYS="${KEEP_DAYS:-7}"
S3="aws --endpoint-url $AWS_ENDPOINT_URL s3"
S3API="aws --endpoint-url $AWS_ENDPOINT_URL s3api"
now=$(date -u +%Y%m%dT%H%M%SZ)
day=$(date -u +%Y/%m/%d)
key="$BACKUP_PREFIX/$day/bhojango-$now.dump"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
t0=$(date +%s)

# Rows per table BEFORE the dump (the restore drill compares them: the dump may only have more), extension tables left out.
psql -qAt -F ' ' <<'SQL' | sort > "$work/db.counts"
SELECT format('SELECT %L, count(*) FROM %I.%I', table_schema || '.' || table_name, table_schema, table_name)
FROM information_schema.tables
WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema', 'tiger', 'tiger_data', 'topology')
  AND NOT EXISTS (SELECT 1 FROM pg_depend d JOIN pg_class c ON c.oid = d.objid
                  WHERE d.deptype = 'e' AND c.relname = table_name AND c.relnamespace = table_schema::regnamespace)
ORDER BY 1 \gexec
SQL
pg_dump -Fc --no-owner --no-privileges -f "$work/db.dump"
# A dump that can't be listed is not a backup.
pg_restore --list "$work/db.dump" > "$work/toc.txt"
tables=$(grep -c 'TABLE DATA' "$work/toc.txt" || true)
sha=$(sha256sum "$work/db.dump" | cut -d' ' -f1)
size=$(wc -c < "$work/db.dump")
echo "$sha" > "$work/db.sha256"

$S3 cp --only-show-errors "$work/db.dump" "s3://$BACKUP_BUCKET/$key"
$S3 cp --only-show-errors "$work/db.sha256" "s3://$BACKUP_BUCKET/$key.sha256"
$S3 cp --only-show-errors "$work/db.counts" "s3://$BACKUP_BUCKET/$key.counts"
printf '{"key":"%s","bytes":%s,"sha256":"%s","tables":%s,"taken_at":"%s"}\n' "$key" "$size" "$sha" "$tables" "$now" > "$work/latest.json"
$S3 cp --only-show-errors "$work/latest.json" "s3://$BACKUP_BUCKET/$BACKUP_PREFIX/latest.json"

# Keep KEEP_DAYS days: delete every dump (and its .sha256/.counts) older than that.
cutoff=$(date -u -d "@$(( $(date +%s) - KEEP_DAYS * 86400 ))" +%Y%m%dT%H%M%SZ 2>/dev/null \
  || date -u -r "$(( $(date +%s) - KEEP_DAYS * 86400 ))" +%Y%m%dT%H%M%SZ)
pruned=0
for old in $($S3API list-objects-v2 --bucket "$BACKUP_BUCKET" --prefix "$BACKUP_PREFIX/" --query 'Contents[].Key' --output text 2>/dev/null | tr '\t' '\n' | grep -E '/bhojango-[0-9]{8}T[0-9]{6}Z\.dump' || true); do
  stamp=$(echo "$old" | sed -E 's/.*bhojango-([0-9]{8})T([0-9]{6})Z\.dump.*/\1\2/')
  if [ "$stamp" -lt "$(echo "$cutoff" | tr -d 'TZ')" ]; then
    $S3 rm --only-show-errors "s3://$BACKUP_BUCKET/$old"; pruned=$((pruned + 1))
  fi
done

echo "db-backup: $key $((size / 1024)) KB, $tables tables, $(awk '{s+=$2} END {print s}' "$work/db.counts") rows, sha256 $(echo "$sha" | cut -c1-16)…, $(( $(date +%s) - t0 )) s; pruned $pruned objects older than $KEEP_DAYS days"
