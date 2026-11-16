#!/bin/sh
# A third city and a third country with no code change (make web-third-city; GitHub e2e.yml).
#   tools/web/third_city.sh
# Builds this checkout and runs the whole stack (backend, web, admin) as its own
# compose project, bhojango-3c, on a clean database with no host ports (so it
# never clashes with `make dev`), seeds it, then runs tools/web/third_city.py in
# the Playwright image on the project's network: the admin launches Meridian
# (Idaho) and a new country, New Zealand (Wellington), in Markets; a partner opens a
# kitchen in each, the admin approves them, and
# the website's directory, city page, sitemap, personal home and kitchen page
# must all pick it up from data. Always torn down with its volumes.
# Screenshots land in docs/screenshots/web-v2/third-city.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
export MSYS_NO_PATHCONV=1
P=bhojango-3c
PW=bhojango-3c-playwright
OUT="$ROOT/docs/screenshots/web-v2/third-city"

# compose.yaml publishes web and admin ports and e2e.compose.yaml only resets the
# backend's: this override (outside the repo) resets the rest.
TMP="$(mktemp -d)"
cat >"$TMP/no-ports.yaml" <<'EOF'
services:
  web:
    ports: !reset []
  admin:
    ports: !reset []
EOF
OVR="$TMP/no-ports.yaml"
command -v cygpath >/dev/null 2>&1 && OVR="$(cygpath -w "$OVR")"

C="docker compose -p $P -f $ROOT/infra/docker/compose.yaml -f $ROOT/infra/docker/e2e.compose.yaml -f $OVR --profile all"

cleanup() {
  docker rm -f "$PW" >/dev/null 2>&1
  timeout 300 $C down -v --remove-orphans >/dev/null 2>&1
  rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

start=$(date +%s)
echo "== building and starting $P (clean database)"
if ! timeout 2400 $C up -d --build --wait; then
  $C logs --tail 60
  exit 1
fi
echo "== seeding"
timeout 300 $C exec -T core-api python /srv/tools/seed/seed.py >/dev/null || { echo "seed failed"; exit 1; }

mkdir -p "$OUT"
echo "== Playwright: tools/web/third_city.py"
timeout 1200 docker run --rm --name "$PW" --network "${P}_default" \
  -v "$ROOT/tools/web:/t:ro" -v "$ROOT/tools/target_guard.py:/guard/target_guard.py:ro" -v "$ROOT/tools/totp_signin.py:/guard/totp_signin.py:ro" -v "$OUT:/out" \
  mcr.microsoft.com/playwright/python:v1.49.0-jammy \
  sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python -u /t/third_city.py"
status=$?
[ $status -eq 0 ] || $C logs --tail 40 core-api web
echo "== third city: exit $status in $(( $(date +%s) - start )) s"
exit $status
