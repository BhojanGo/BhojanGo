#!/bin/sh
# Every website page in every language at 360 and 1440 px against `make dev` (R27):
# no sideways scroll, no catalog text cut off (tools/web/i18n_layout.py).
#   tools/web/i18n_layout.sh
# Runs in the Playwright image on the compose network; failures' screenshots and
# i18n-layout.md land in docs/screenshots/web-i18n.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-bhojango}" MSYS_NO_PATHCONV=1
mkdir -p "$ROOT/docs/screenshots/web-i18n"
docker run --rm --network "${COMPOSE_PROJECT_NAME}_default" \
  -v "$ROOT/tools/web:/t:ro" -v "$ROOT/packages/i18n/messages:/messages:ro" -v "$ROOT/docs/screenshots/web-i18n:/out" \
  -e MESSAGES=/messages -e OUT=/out \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/i18n_layout.py /out"
