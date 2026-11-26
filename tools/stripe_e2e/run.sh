#!/bin/sh
# R44: every case also runs in a round's full fresh run (the functional report's Stripe rows come from this PR's run).
# Stripe test-mode end-to-end (QA_JOB=stripe-e2e on the Railway qa-runner; see
# tools/railway/qa-job.sh). Real Stripe in TEST mode, never QA's data:
#   1. a throwaway database on the QA Postgres server (bhojango_stripe_e2e_<time>),
#      PostGIS, migrations to head and the base seed (fixed test passwords);
#      Redis database 11 (flushed before and after);
#   2. core-api inside this container on localhost:8011 against them, with
#      PAYMENT_PROVIDER=auto (US -> Stripe), TAX_PROVIDER=auto (Stripe Tax);
#   3. the Stripe CLI (pinned release, checksum-verified) forwards the account's
#      webhooks to it; its signing secret becomes STRIPE_WEBHOOK_SECRET;
#   4. tools/stripe_e2e/harness.py runs every case file (tools/stripe_e2e/test_*.py),
#      PASS/FAIL per case and one result line;
#   5. everything is torn down (processes stopped, database dropped, Redis 11 flushed).
# Hold mode (manual checks against the same stack: the headed 3-D Secure check, the apps on an
# emulator, admin Finance): STRIPE_E2E_HOLD_MINUTES=N binds core-api on 0.0.0.0 (give the runner
# a temporary Railway domain to port $PORT) and keeps the stack up N minutes (at most 90) after the
# cases (STRIPE_E2E_CASES=none runs no case first); then it is torn down as usual. Databases a
# killed run left behind (older than 3 hours) are dropped when the next run starts.
# Needs STRIPE_SECRET_KEY (sk_test_...) and STRIPE_PUBLISHABLE_KEY (pk_test_...) as
# sealed variables on the runner; without them it prints "SKIPPED: no Stripe test keys".
# Live keys are refused. Keys are never printed.
set -u
ROOT="${REPO_ROOT:-/repo}"
HERE="$ROOT/tools/stripe_e2e"
STRIPE_CLI_VERSION=1.55.3
STRIPE_CLI_SHA256=a894f7891eac5eabb67a5ad5b4820a236626a805b9be544fb4c6e41c5ad91043
PORT="${STRIPE_E2E_PORT:-8011}"
HOLD="${STRIPE_E2E_HOLD_MINUTES:-0}"
case "$HOLD" in ''|*[!0-9]*) HOLD=0 ;; esac
[ "$HOLD" -gt 90 ] && HOLD=90
BIND=127.0.0.1; [ "$HOLD" -gt 0 ] && BIND=0.0.0.0

case "${STRIPE_SECRET_KEY:-}" in
  sk_test_*|rk_test_*) ;;
  "") echo "stripe-e2e: SKIPPED: no Stripe test keys (set STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY on the runner)"; exit 0 ;;
  *) echo "stripe-e2e: REFUSED: STRIPE_SECRET_KEY is not a test-mode key"; exit 3 ;;
esac
case "${STRIPE_PUBLISHABLE_KEY:-}" in
  pk_test_*) ;;
  *) echo "stripe-e2e: REFUSED: STRIPE_PUBLISHABLE_KEY missing or not a test-mode key"; exit 3 ;;
esac

WORK="$(mktemp -d)"
pg_url() { echo "$1" | sed 's/+asyncpg//'; }
DB="bhojango_stripe_e2e_test_$(date +%s)"  # R42: a test database by name (tools/target_guard.py)
BASE_PG="$(pg_url "${DATABASE_URL:?DATABASE_URL (the QA Postgres server) is needed to create a throwaway database}")"
# CREATE/DROP DATABASE run on the server's maintenance database by a role with CREATEDB;
# STRIPE_E2E_ADMIN_DATABASE_URL overrides it (e.g. the postgres superuser's URL).
SERVER_PG="$(pg_url "${STRIPE_E2E_ADMIN_DATABASE_URL:-}")"
[ -n "$SERVER_PG" ] || SERVER_PG="$(echo "$BASE_PG" | sed 's#/[^/?]*\(?.*\)\{0,1\}$#/postgres\1#')"
E2E_PG="$(echo "$BASE_PG" | sed "s#/[^/?]*\(?.*\)\{0,1\}\$#/$DB\1#")"
E2E_DB_URL="$(echo "$E2E_PG" | sed 's#^postgresql://#postgresql+asyncpg://#')"
E2E_REDIS="$(echo "${REDIS_URL:?REDIS_URL is needed}" | sed 's#/[0-9]*$##')/11"
API_PID=""; CLI_PID=""

flush_redis() {
  uv run --frozen python -c "
import asyncio, sys
import redis.asyncio as redis
async def go():
    r = redis.from_url(sys.argv[1]); await r.flushdb(); await r.aclose()
asyncio.run(go())" "$E2E_REDIS" >/dev/null 2>&1 || true
}
cleanup() {
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null
  [ -n "$CLI_PID" ] && kill "$CLI_PID" 2>/dev/null
  sleep 1
  psql "$SERVER_PG" -q -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB'" >/dev/null 2>&1
  psql "$SERVER_PG" -q -c "DROP DATABASE IF EXISTS \"$DB\"" >/dev/null 2>&1 && echo "stripe-e2e: dropped $DB"
  flush_redis
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

# The child processes are a throwaway test stack, not QA: their own name, no QA identity.
e2e_env() {
  env -u RAILWAY_ENVIRONMENT_NAME -u QA_JOB \
    JWT_PRIVATE_KEY="$E2E_JWT_KEY" APP_ENV=e2e DATABASE_URL="$E2E_DB_URL" REDIS_URL="$E2E_REDIS" EVENT_BUS=redis EVENT_BUS_REDIS_URL="$E2E_REDIS" \
    JWT_SECRET_KEY="$JWT_SECRET" PAYMENT_PROVIDER=auto TAX_PROVIDER=auto PAYOUT_PROVIDER="${STRIPE_E2E_PAYOUT_PROVIDER:-auto}" \
    SMS_PROVIDER=log PUSH_PROVIDER=log EMAIL_PROVIDER=log OTP_FIXED_CODE=123456 \
    STRIPE_WEBHOOK_SECRET="${WHSEC:-}" INTERNAL_SERVICE_SECRET="$E2E_INTERNAL" "$@"
}
JWT_SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
# R43: this run's own service-to-service secret (the harness assigns the rider as realtime would; never QA's)
E2E_INTERNAL="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
# Outside development and test core-api needs a real signing key: a throwaway one for this run only
# (never QA's: the test stack must not mint tokens QA would accept).
E2E_JWT_KEY="$(uv run --frozen python -c 'from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization as s
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
print(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()).decode())')"   || { echo "stripe-e2e: FAIL: could not make a signing key"; exit 1; }

# Throwaway databases a killed run (e.g. a runner deleted mid-hold) left behind: older than 3 hours.
for old in $(psql "$SERVER_PG" -qAtX -c "SELECT datname FROM pg_database WHERE datname LIKE 'bhojango_stripe_e2e_%'" 2>/dev/null); do
  ts="${old#bhojango_stripe_e2e_}"
  case "$ts" in ''|*[!0-9]*) continue ;; esac
  if [ "$ts" -lt $(( $(date +%s) - 10800 )) ]; then
    psql "$SERVER_PG" -q -c "DROP DATABASE IF EXISTS \"$old\" WITH (FORCE)" >/dev/null 2>&1 && echo "stripe-e2e: dropped a stale $old"
  fi
done
echo "stripe-e2e: database $DB on the QA server (dropped at the end), Redis db 11"
psql "$SERVER_PG" -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE \"$DB\"" \
  && psql "$E2E_PG" -v ON_ERROR_STOP=1 -q -f "$ROOT/infra/docker/db/init.sql" >/dev/null \
  || { echo "stripe-e2e: FAIL: could not create the throwaway database"; exit 1; }
flush_redis
e2e_env uv run --frozen alembic upgrade head >"$WORK/migrate.log" 2>&1 \
  || { echo "stripe-e2e: FAIL: migrations"; tail -20 "$WORK/migrate.log"; exit 1; }
e2e_env uv run --frozen python "$ROOT/tools/seed/seed.py" >"$WORK/seed.log" 2>&1 \
  || { echo "stripe-e2e: FAIL: seed"; tail -20 "$WORK/seed.log"; exit 1; }
# Kitchens and cities open around the clock (as the integration suite does), so the run doesn't depend on the hour.
psql "$E2E_PG" -v ON_ERROR_STOP=1 -q \
  -c "UPDATE cities SET service_hours = '{\"open\": \"00:00\", \"close\": \"00:00\"}'::jsonb WHERE service_hours IS NOT NULL" \
  -c "INSERT INTO store_hour_overrides (id, restaurant_id, day, closed, opens, closes, note)
      SELECT gen_random_uuid(), r.id, current_date + d, false, '00:00', '00:00', 'stripe e2e: open all day'
      FROM restaurants r CROSS JOIN generate_series(-2, 3) d
      ON CONFLICT (restaurant_id, day) DO UPDATE SET closed = false, opens = '00:00', closes = '00:00'" \
  || { echo "stripe-e2e: FAIL: opening hours"; exit 1; }

# The Stripe CLI: pinned release, checksum-verified.
echo "stripe-e2e: Stripe CLI $STRIPE_CLI_VERSION"
TGZ="$WORK/stripe.tgz"
uv run --frozen python - "$STRIPE_CLI_VERSION" "$TGZ" <<'EOF' || { echo "stripe-e2e: FAIL: could not download the Stripe CLI"; exit 1; }
import sys, urllib.request
v, out = sys.argv[1], sys.argv[2]
urllib.request.urlretrieve(f"https://github.com/stripe/stripe-cli/releases/download/v{v}/stripe_{v}_linux_x86_64.tar.gz", out)
EOF
echo "$STRIPE_CLI_SHA256  $TGZ" | sha256sum -c - >/dev/null || { echo "stripe-e2e: FAIL: Stripe CLI checksum mismatch"; exit 1; }
tar -xzf "$TGZ" -C "$WORK" stripe && STRIPE="$WORK/stripe"
EVENTS="$(uv run --frozen python -c "from core_api.modules.payments.service.stripe_svc import WEBHOOK_EVENTS; print(','.join(WEBHOOK_EVENTS))")"
EVENTS="$EVENTS${STRIPE_E2E_EXTRA_EVENTS:+,$STRIPE_E2E_EXTRA_EVENTS}"
WHSEC="$("$STRIPE" listen --api-key "$STRIPE_SECRET_KEY" --print-secret 2>/dev/null)"
case "$WHSEC" in whsec_*) ;; *) echo "stripe-e2e: FAIL: no webhook signing secret from the Stripe CLI"; exit 1 ;; esac
"$STRIPE" listen --api-key "$STRIPE_SECRET_KEY" --events "$EVENTS" \
  --forward-to "localhost:$PORT/api/v1/payments/stripe/webhook" >"$WORK/listen.log" 2>&1 &
CLI_PID=$!

e2e_env uv run --frozen uvicorn core_api.main:app --host "$BIND" --port "$PORT" >"$WORK/api.log" 2>&1 &
API_PID=$!
i=0
until uv run --frozen python -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1], timeout=3)" "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; do
  i=$((i + 1)); [ $i -ge 60 ] && { echo "stripe-e2e: FAIL: core-api didn't start"; tail -30 "$WORK/api.log"; exit 1; }
  sleep 2
done
i=0
until grep -q "Ready!" "$WORK/listen.log"; do
  i=$((i + 1)); [ $i -ge 30 ] && { echo "stripe-e2e: FAIL: stripe listen not ready"; sed 's/whsec_[A-Za-z0-9]*/whsec_***/g' "$WORK/listen.log" | tail -10; exit 1; }
  sleep 1
done
echo "stripe-e2e: core-api on :$PORT, Stripe CLI forwarding $EVENTS"

# Headless Chromium for the Payment Element and 3-D Secure cases (pinned Playwright).
# The qa-runner image installs Chromium and its libraries at build time (PLAYWRIGHT_BROWSERS_PATH,
# infra/railway/qa-runner.Dockerfile, same version); elsewhere it is installed here.
PW="playwright==1.49.0"  # = infra/railway/qa-runner.Dockerfile
if ls -d "${PLAYWRIGHT_BROWSERS_PATH:-/nonexistent}"/chromium* >/dev/null 2>&1; then
  echo "stripe-e2e: Chromium from the image (${PLAYWRIGHT_BROWSERS_PATH})"
elif ! uv run --frozen --with "$PW" python -m playwright install --with-deps chromium >"$WORK/playwright.log" 2>&1; then
  echo "stripe-e2e: Playwright/Chromium could not be installed; the browser cases will fail. playwright.log (last 25 lines):"
  tail -25 "$WORK/playwright.log"
fi
rc=0
if [ "${STRIPE_E2E_CASES:-}" != none ]; then
  STRIPE_E2E_CORE="http://127.0.0.1:$PORT" STRIPE_E2E_PSQL="$E2E_PG" STRIPE_E2E_WORK="$WORK" \
    e2e_env uv run --frozen --with "$PW" python -I "$HERE/harness.py" "$@"
  rc=$?
fi
if [ "$HOLD" -gt 0 ]; then
  echo "stripe-e2e: HOLD core-api on 0.0.0.0:$PORT for $HOLD minutes (until $(date -u -d "+$HOLD min" +%H:%MZ 2>/dev/null)), then teardown"
  end=$(( $(date +%s) + HOLD * 60 ))
  while [ "$(date +%s)" -lt "$end" ] && kill -0 "$API_PID" 2>/dev/null; do sleep 15; done
  kill -0 "$API_PID" 2>/dev/null || { echo "stripe-e2e: core-api stopped during the hold"; rc=1; }
  echo "stripe-e2e: HOLD over"
fi
if [ $rc -ne 0 ]; then
  echo "stripe-e2e: core-api log (last 60 lines)"; sed 's/sk_test_[A-Za-z0-9]*/sk_test_***/g; s/whsec_[A-Za-z0-9]*/whsec_***/g' "$WORK/api.log" | tail -60
fi
exit $rc
