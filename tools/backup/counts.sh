#!/bin/sh
# Exact row count of every table in the stack's database, one "schema.table count"
# per line, sorted: the fingerprint a restore is checked against. Tables that
# belong to an extension (PostGIS spatial_ref_sys) are left out: they're not our data.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose ${COMPOSE_FILES:--f $ROOT/infra/docker/compose.yaml}"
$COMPOSE exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qAt -F " " <<SQL
SELECT format('"'"'SELECT %L, count(*) FROM %I.%I'"'"', table_schema || '"'"'.'"'"' || table_name, table_schema, table_name)
FROM information_schema.tables
WHERE table_type = '"'"'BASE TABLE'"'"' AND table_schema NOT IN ('"'"'pg_catalog'"'"', '"'"'information_schema'"'"', '"'"'tiger'"'"', '"'"'tiger_data'"'"', '"'"'topology'"'"')
  AND NOT EXISTS (SELECT 1 FROM pg_depend d JOIN pg_class c ON c.oid = d.objid
                  WHERE d.deptype = '"'"'e'"'"' AND c.relname = table_name AND c.relnamespace = table_schema::regnamespace)
ORDER BY 1 \gexec
SQL' | sort
