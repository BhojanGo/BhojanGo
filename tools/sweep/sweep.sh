#!/bin/sh
# R41 validation sweep: every website and admin page, a US and an India user, 1440 and 390 px, the same checks on each
# (tools/sweep/sweep_web.py). Screenshots and sweep-web.json land in docs/screenshots/sweep (OUT to change it).
#   tools/sweep/sweep.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose -f $ROOT/infra/docker/compose.yaml"
OUT="${OUT:-$ROOT/docs/screenshots/sweep}"
mkdir -p "$OUT"
python "$ROOT/tools/mobile/hours.py" open >/dev/null
$COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'otp_attempts:*' | xargs -r redis-cli -n 0 del" >/dev/null
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/sweep:/t:ro" -v "$ROOT/tools/target_guard.py:/guard/target_guard.py:ro" -v "$ROOT/tools/totp_signin.py:/guard/totp_signin.py:ro" \
  -v "$OUT:/out" mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/${SCRIPT:-sweep_web.py}"  # R42: SCRIPT=functional/run_web.py
status=$?
python "$ROOT/tools/mobile/hours.py" close >/dev/null
exit $status
