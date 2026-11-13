#!/bin/sh
# Pilot dress rehearsal: a 2-hour Boise dinner rush on `make dev` + `make observe`.
#   tools/soak/run.sh                 # 120 minutes, 150 orders (SOAK_MINUTES, SOAK_ORDERS to change)
# Needs the stack up (make dev && make observe). Uses COMPOSE_PROJECT_NAME
# (default bhojango). Writes to tools/soak/out/<UTC time>/ (git-ignored):
#   soak.log, soak-result.json (every order), samples.csv (once a minute:
#   memory/CPU per container, Postgres connections, Redis clients and memory,
#   open WebSockets), alerts.json, log-errors.txt, then report.json.
# Then: python tools/soak/report.py <that dir>  (run.sh does it at the end).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
P="$COMPOSE_PROJECT_NAME"
NET="${P}_default"
MINUTES="${SOAK_MINUTES:-120}"
RIDERS="${SOAK_RIDERS:-8}"
BATCHING="${SOAK_BATCHING:-off}"   # on: Boise has live batching for this run (task 43)
ORDERS="${SOAK_ORDERS:-150}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$ROOT/tools/soak/out/$STAMP"
mkdir -p "$OUT"
START_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "$START_ISO" > "$OUT/started_at"
DB_URL="postgresql+asyncpg://bhojango:bhojango_dev@postgres:5432/bhojango"

echo "== build the soak image (backend + its dependencies)"
docker build -q -f "$ROOT/infra/docker/test.Dockerfile" --target migrations -t bhojango-soak "$ROOT" >/dev/null || exit 1
OPTS="--rm --network $NET -e SOAK_RIDERS=$RIDERS -e DATABASE_URL=$DB_URL -e PYTHONPATH=/repo/backend -v $ROOT/tools:/repo/tools:ro -v $OUT:/out -w /repo/backend"
RUN="docker run $OPTS bhojango-soak"

echo "== people (riders 4-8, customers 6-40) and opening hours around the clock"
$RUN uv run --frozen python /repo/tools/soak/setup.py || exit 1
$RUN uv run --frozen python -c "
import asyncio
from core_api.integration.conftest import open_all_day
from shared.db import engine
async def go():
    await open_all_day(); await engine.dispose()
asyncio.run(go())" || exit 1

echo "== batching in Boise: $BATCHING"
$RUN uv run --frozen python /repo/tools/soak/batching_switch.py "$BATCHING" || exit 1

echo "== sampler (once a minute) -> samples.csv"
sh "$ROOT/tools/soak/sample.sh" "$P" "$OUT/samples.csv" &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

echo "== soak: $MINUTES minutes, $ORDERS orders, $RIDERS riders, batching $BATCHING (log: $OUT/soak.log)"
echo "riders=$RIDERS batching=$BATCHING" > "$OUT/settings"
# Bounded: the window plus 30 minutes for stragglers and the write-up.
timeout $(( (${MINUTES%.*} + 30) * 60 )) docker run $OPTS -e SOAK_MINUTES="$MINUTES" -e SOAK_ORDERS="$ORDERS" -e SOAK_OUT=/out/soak-result.json \
  bhojango-soak uv run --frozen python /repo/tools/soak/soak.py > "$OUT/soak.log" 2>&1
echo "soak exit: $?"
[ "$BATCHING" = "on" ] && $RUN uv run --frozen python /repo/tools/soak/batching_switch.py off
kill $SAMPLER 2>/dev/null
END_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "$END_ISO" > "$OUT/ended_at"

echo "== alerts fired during the window -> alerts.json"
docker compose -p "$P" exec -T postgres psql -U bhojango -d bhojango -qAt -c \
  "SELECT coalesce(json_agg(a ORDER BY a.starts_at), '[]') FROM (SELECT name, city, status, severity, summary, starts_at, ends_at, updated_at FROM ops_alerts WHERE updated_at >= '$START_ISO') a" \
  > "$OUT/alerts.json" 2>/dev/null || echo "[]" > "$OUT/alerts.json"
curl -s "http://localhost:${ALERTMANAGER_PORT:-9093}/api/v2/alerts" > "$OUT/alertmanager-now.json" 2>/dev/null || true

echo "== waiting for a rider (dispatch start -> rider assigned) -> rider-waits.json"
# "overtakes": pairs where an order that started looking later got a rider over 20 s sooner (fairness).
docker compose -p "$P" exec -T postgres psql -U bhojango -d bhojango -qAt -c "
WITH h AS (SELECT o.id, o.rider_assigned_at AS a,
  (SELECT (e->>'at')::timestamptz FROM jsonb_array_elements(o.status_history) e WHERE e->>'status' IN ('almost_ready','ready') ORDER BY e->>'at' LIMIT 1) AS d
  FROM orders o WHERE o.created_at >= '$START_ISO' AND o.rider_assigned_at IS NOT NULL)
SELECT json_build_object('orders', count(*),
  'median_min', round((extract(epoch from percentile_cont(0.5) WITHIN GROUP (ORDER BY a - d)) / 60)::numeric, 1),
  'p90_min', round((extract(epoch from percentile_cont(0.9) WITHIN GROUP (ORDER BY a - d)) / 60)::numeric, 1),
  'max_min', round((extract(epoch from max(a - d)) / 60)::numeric, 1),
  'overtakes', (SELECT count(*) FROM h x JOIN h y ON x.d < y.d AND x.a > y.a + interval '20 seconds'))
FROM h" > "$OUT/rider-waits.json" 2>/dev/null || echo "{}" > "$OUT/rider-waits.json"

echo "== errors in the logs -> log-errors.txt"
for svc in core-api realtime worker web admin postgres redis; do
  docker compose -p "$P" logs --no-color --since "$START_ISO" --until "$END_ISO" "$svc" 2>/dev/null \
    | grep -E '"level": ?"(error|critical)"|Traceback|\bERROR\b|\bFATAL\b|Exception' | sed "s/^/[$svc] /"
done > "$OUT/log-errors.txt"
wc -l < "$OUT/log-errors.txt"

python "$ROOT/tools/soak/report.py" "$OUT"
