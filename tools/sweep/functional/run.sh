#!/bin/sh
# R42 functional validation of the website and the admin console (tools/sweep/functional/run_web.py), on a local
# stack that runs on a test database (tools/target_guard.py refuses anything else):
#   1. every function as the US and India users (core-api up);
#   2. core-api stopped: every page's "API down" state; core-api started again.
# Results: OUT/functional-up.json, OUT/functional-down.json and screenshots (default qa-artifacts/r42/functional).
#   POSTGRES_DB=bhojango_e2e_test COMPOSE_PROJECT_NAME=<project> tools/sweep/functional/run.sh [up|down]
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
OUT="${OUT:-$ROOT/qa-artifacts/r42/functional}"
DB="${POSTGRES_DB:-}"
case "$DB" in *test*) ;; *) echo "REFUSED: POSTGRES_DB must name the stack's test database (got '$DB')" >&2; exit 3 ;; esac
mkdir -p "$OUT"
COMPOSE="docker compose -p $COMPOSE_PROJECT_NAME -f $ROOT/infra/docker/compose.yaml"
run() {
  docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" -e PHASE="$1" -e POSTGRES_DB="$DB" -e ONLY="${ONLY:-.*}" \
    -v "$ROOT/tools/sweep:/t:ro" -v "$ROOT/tools/target_guard.py:/guard/target_guard.py:ro" -v "$ROOT/tools/totp_signin.py:/guard/totp_signin.py:ro" \
    -v "$OUT:/out" mcr.microsoft.com/playwright/python:v1.49.0-jammy \
    sh -c "pip -q install playwright==1.49.0 'psycopg[binary]==3.2.3' tzdata==2025.2 >/dev/null 2>&1; python /t/functional/run_web.py"
}
status=0
if [ "${1:-all}" != "down" ]; then
  python "$ROOT/tools/mobile/hours.py" open >/dev/null
  $COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'otp_attempts:*' | xargs -r redis-cli -n 0 del" >/dev/null
  run up || status=1
fi
if [ "${1:-all}" != "up" ]; then
  $COMPOSE stop core-api >/dev/null
  run down || status=1
  $COMPOSE start core-api >/dev/null
  $COMPOSE up -d --wait core-api >/dev/null 2>&1
fi
python "$ROOT/tools/mobile/hours.py" close >/dev/null 2>&1
exit $status
