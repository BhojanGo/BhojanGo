#!/bin/sh
# The web and admin Playwright suites (tools/web/e2e_web.py, tools/admin/e2e_admin.py)
# against the Railway QA URLs instead of make dev.
#   QA_WEB=https://... QA_ADMIN=https://... QA_CORE=https://... QA_RT=https://... \
#   E2E_LOGINS_FILE=/path/outside/the/repo/BhojanGo_QA_Logins.txt tools/railway/playwright-qa.sh [out-dir]
# The logins file (from the QA seed) is mounted read-only; screenshots go to out-dir.
# Restaurants must be open: run `tools/railway/qa-runner.sh job hours` first.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
OUT="${1:-$ROOT/backups/playwright-qa}"
mkdir -p "$OUT/web" "$OUT/admin"
OUT_W="$(cd "$OUT" && (pwd -W 2>/dev/null || pwd))"
LOGINS_DIR="$(cd "$(dirname "$E2E_LOGINS_FILE")" && (pwd -W 2>/dev/null || pwd))"
LOGINS_NAME="$(basename "$E2E_LOGINS_FILE")"
export MSYS_NO_PATHCONV=1
status=0
for suite in web admin; do
  docker run --rm -e QA_WEB -e QA_ADMIN -e QA_CORE -e QA_RT -e E2E_LOGINS_FILE="/secrets/$LOGINS_NAME" \
    -v "$ROOT/tools/$suite:/t:ro" -v "$LOGINS_DIR/$LOGINS_NAME:/secrets/$LOGINS_NAME:ro" -v "$OUT_W/$suite:/out" \
    mcr.microsoft.com/playwright/python:v1.49.0-jammy \
    sh -c "pip -q install playwright==1.49.0 >/dev/null 2>&1; python /t/e2e_$suite.py" || status=1
done
exit $status
