#!/bin/sh
# Playwright run of the admin console against `make dev` (P21).
#   tools/admin/e2e.sh
# Opens Hyderabad around the clock for the run (tools/mobile/hours.py), resets
# OTP send counters, and runs tools/admin/e2e_admin.py in the Playwright image on
# the compose network. Screenshots land in docs/screenshots/admin.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose -f $ROOT/infra/docker/compose.yaml"
mkdir -p "$ROOT/docs/screenshots/admin"
python "$ROOT/tools/mobile/hours.py" open >/dev/null
$COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'otp_attempts:*' | xargs -r redis-cli -n 0 del" >/dev/null
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/admin:/t:ro" -v "$ROOT/docs/screenshots/admin:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/e2e_admin.py"
status=$?
python "$ROOT/tools/mobile/hours.py" close >/dev/null
exit $status
