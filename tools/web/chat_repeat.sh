#!/bin/sh
# The website's live-chat check N times in a row (R7), against `make dev`, seeded.
#   tools/web/chat_repeat.sh [N]     (default 50)
# Opens Hyderabad around the clock for the run (tools/mobile/hours.py), then runs
# tools/web/chat_repeat.py in the Playwright image on the compose network.
# A failed round's screenshot lands in docs/screenshots/web/chat-fail-<n>.png.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
mkdir -p "$ROOT/docs/screenshots/web"
python "$ROOT/tools/mobile/hours.py" open >/dev/null
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/web:/t:ro" -v "$ROOT/tools/target_guard.py:/guard/target_guard.py:ro" -v "$ROOT/tools/totp_signin.py:/guard/totp_signin.py:ro" -v "$ROOT/docs/screenshots/web:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/chat_repeat.py ${1:-50}"
status=$?
python "$ROOT/tools/mobile/hours.py" close >/dev/null
exit $status
