#!/bin/sh
# Screenshots of every designed website page on seed data, then the design comparison.
#   COMPOSE_PROJECT_NAME=bhojango-e2e sh tools/web/screens_v2.sh
# Needs the stack up (make dev). Opens Hyderabad and Boise around the clock for the
# run (tools/mobile/hours.py), clears /discover's short cache, runs
# tools/web/screens_v2.py in the Playwright image on the compose network (PNGs in
# docs/screenshots/web-v2/raw), then tools/web/design_compare.py writes the
# side-by-side images to docs/screenshots/web-v2 and prints the score table.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
COMPOSE="docker compose -f $ROOT/infra/docker/compose.yaml"
mkdir -p "$ROOT/docs/screenshots/web-v2/raw"
python "$ROOT/tools/mobile/hours.py" open >/dev/null
$COMPOSE exec -T redis sh -c "redis-cli -n 0 --scan --pattern 'discover:*' | xargs -r redis-cli -n 0 del" >/dev/null
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/web:/t:ro" -v "$ROOT/docs/screenshots/web-v2/raw:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/screens_v2.py"
status=$?
python "$ROOT/tools/mobile/hours.py" close >/dev/null
[ $status -eq 0 ] && python "$ROOT/tools/web/design_compare.py" "$ROOT/docs/screenshots/web-v2/raw" "$ROOT/docs/screenshots/web-v2"
exit $status
