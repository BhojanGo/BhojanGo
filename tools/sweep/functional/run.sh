#!/bin/sh
# R42 functional validation of the website and the admin console (tools/sweep/functional/run_web.py), on a local
# stack that runs on a test database (tools/target_guard.py refuses anything else):
#   1. every function as the US and India users (core-api up);
#   2. core-api stopped: every page's "API down" state; core-api started again.
# Results: OUT/functional-up.json, OUT/functional-down.json and screenshots (default qa-artifacts/r42/functional).
#   3. (R44) nothing the run made is still live and no test-named rows (leftovers.py; LEFTOVERS=0 skips it).
#   POSTGRES_DB=bhojango_e2e_test COMPOSE_PROJECT_NAME=<project> tools/sweep/functional/run.sh [up|down|leftovers snapshot|check]
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
OUT="${OUT:-$ROOT/qa-artifacts/r42/functional}"
DB="${POSTGRES_DB:-}"
case "$DB" in *test*) ;; *) echo "REFUSED: POSTGRES_DB must name the stack's test database (got '$DB')" >&2; exit 3 ;; esac
mkdir -p "$OUT"
COMPOSE="docker compose -p $COMPOSE_PROJECT_NAME -f $ROOT/infra/docker/compose.yaml"
run() {  # run PHASE [script args]: run_web.py by default; R44: leftovers.py snapshot|check
  docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" -e PHASE="$1" -e POSTGRES_DB="$DB" -e ONLY="${ONLY:-.*}" \
    -v "$ROOT/tools/sweep:/t:ro" -v "$ROOT/tools/target_guard.py:/guard/target_guard.py:ro" -v "$ROOT/tools/totp_signin.py:/guard/totp_signin.py:ro" \
    -v "$OUT:/out" mcr.microsoft.com/playwright/python:v1.49.0-jammy \
    sh -c "pip -q install playwright==1.49.0 'psycopg[binary]==3.2.3' tzdata==2025.2 >/dev/null 2>&1; cd /t/functional && python ${2:-run_web.py} ${3:-}"
}
status=0
# R44: what the seeded stack has before the run; after it, nothing the run made may still be live (leftovers.py).
# LEFTOVERS=0 skips both (a later step, e.g. the Maestro flows, runs the check instead: run.sh leftovers check).
if [ "${1:-all}" = leftovers ]; then run up leftovers.py "${2:-check}"; exit $?; fi
[ "${LEFTOVERS:-1}" = 1 ] && [ "${1:-all}" = all ] && { run up leftovers.py snapshot || status=1; }
if [ "${1:-all}" != "down" ]; then
  python "$ROOT/tools/mobile/hours.py" open >/dev/null
  $COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'otp_attempts:*' | xargs -r redis-cli -n 0 del" >/dev/null
  run up || status=1
fi
if [ "${1:-all}" != "up" ]; then
  $COMPOSE stop core-api >/dev/null
  run down || status=1
  $COMPOSE start core-api >/dev/null
  $COMPOSE up -d --wait --no-recreate core-api >/dev/null 2>&1  # the same container: never re-pointed at another database
fi
[ "${LEFTOVERS:-1}" = 1 ] && [ "${1:-all}" = all ] && { run up leftovers.py check || status=1; }
[ "${KEEP_HOURS:-0}" = 1 ] || python "$ROOT/tools/mobile/hours.py" close >/dev/null 2>&1  # KEEP_HOURS=1: another run (Maestro) still needs them open
exit $status
