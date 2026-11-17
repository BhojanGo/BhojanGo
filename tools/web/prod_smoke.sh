#!/bin/sh
# Production build smoke test (R9 item 8): runs tools/web/prod_smoke.py in the Playwright
# image on the compose network, against web and admin built with APP_ENV=production
# (infra/docker/compose.prod-smoke.yaml). Screenshots land in docs/screenshots/prod-smoke.
#   tools/web/prod_smoke.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
mkdir -p "$ROOT/docs/screenshots/prod-smoke"
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/web:/t:ro" -v "$ROOT/docs/screenshots/prod-smoke:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/prod_smoke.py"
