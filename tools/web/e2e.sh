#!/bin/sh
# Playwright run of the customer web against `make dev` (P20).
#   tools/web/e2e.sh
# Opens Hyderabad and Boise around the clock for the run (tools/mobile/hours.py),
# resets OTP send counters and the discover cache, and runs tools/web/e2e_web.py in the Playwright image on
# the compose network. Screenshots land in docs/screenshots/web.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose -f $ROOT/infra/docker/compose.yaml"
mkdir -p "$ROOT/docs/screenshots/web"
python "$ROOT/tools/mobile/hours.py" open >/dev/null
# OTP send counters, and /discover's short cache (it may still hold "closed").
for pattern in 'otp_attempts:*' 'discover:*'; do
  $COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern '$pattern' | xargs -r redis-cli -n 0 del" >/dev/null
done
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/web:/t:ro" -v "$ROOT/tools/target_guard.py:/guard/target_guard.py:ro" -v "$ROOT/tools/totp_signin.py:/guard/totp_signin.py:ro" -v "$ROOT/docs/screenshots/web:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 tzdata==2025.2 >/dev/null 2>&1; python /t/e2e_web.py"
status=$?
python "$ROOT/tools/mobile/hours.py" close >/dev/null
exit $status
