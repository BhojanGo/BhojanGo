#!/bin/sh
# One QA job per deploy of the qa-runner service (infra/railway/qa-runner.Dockerfile),
# chosen by QA_JOB. Runs inside the QA environment's private network, prints a
# result line, and exits (the service's restart policy is NEVER, so it costs
# nothing between jobs). Secrets come from Railway references; nothing secret
# is printed.
#
# QA gets read-only checks and demo data, never tests: tests run locally (make dev,
# make ci) and in CI, and tools/target_guard.py refuses anything that would write
# test data here.
#   reset        rebuild QA's database from scratch: drop and recreate the public
#                schema (PostGIS re-created), migrations to head, Redis database 0
#                cleared, then the base seed and the demo seed with random
#                passwords (logins to the private bucket, QA_LOGINS_KEY). Refused
#                unless RAILWAY_ENVIRONMENT_NAME is QA and APP_ENV is qa.
#   seed         the base seed (Hyderabad + Boise) with random passwords; the
#                logins go to the private uploads bucket, never to the log
#   demo         the demo seed on top of it (tools/seed/demo.py); its logins are
#                added to the same bucket file
#   checks       read-only: each backend's /health over the private network,
#                migrations at head and `alembic check` against the QA database
#   hours        open the seed cities and restaurants around the clock (for demos)
#   g1, integration
#                refused (exit 3): the G1 and integration suites write test data.
#                They run in make ci (ci-e2e, ci-migrations) and in CI.
set -u
cd /repo/backend
RUN="${QA_JOB:-none}"      # <job>#<tag>: the tag tells one run's result from the last one's
JOB="${RUN%%#*}"
KEY="${QA_LOGINS_KEY:-qa-private/seed-logins.tsv}"
echo "qa-job: $RUN (commit ${RAILWAY_GIT_COMMIT_SHA:-local})"
pg_url() { echo "$1" | sed 's/+asyncpg//'; }

case "$JOB" in
  reset)
    # Both names must say QA: Railway's own (any case) and APP_ENV.
    rw_env="$(printf '%s' "${RAILWAY_ENVIRONMENT_NAME:-}" | tr '[:upper:]' '[:lower:]')"
    if [ "$rw_env" != "qa" ] || [ "${APP_ENV:-}" != "qa" ]; then
      echo "reset: REFUSED: RAILWAY_ENVIRONMENT_NAME='${RAILWAY_ENVIRONMENT_NAME:-}' APP_ENV='${APP_ENV:-}' (only QA is ever reset)"
      rc=3
    else
      PSQL="$(pg_url "$DATABASE_URL")"
      echo "reset: dropping and recreating the public schema"
      # Other sessions (the services' pools) are closed first so the drop doesn't wait on
      # their locks; the services reconnect by themselves.
      psql "$PSQL" -v ON_ERROR_STOP=1 -q \
          -c "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()" \
          -c "DROP SCHEMA public CASCADE" -c "CREATE SCHEMA public" -c "GRANT ALL ON SCHEMA public TO PUBLIC" \
        && psql "$PSQL" -v ON_ERROR_STOP=1 -q -f /repo/infra/docker/db/init.sql \
        && psql "$PSQL" -v ON_ERROR_STOP=1 -qAt -c "SELECT 'reset: postgis ' || extversion FROM pg_extension WHERE extname = 'postgis'" \
        && uv run --frozen alembic upgrade head \
        && uv run --frozen python -c "
import asyncio
import redis.asyncio as redis
from shared.config import get_settings
async def go():
    r = redis.from_url(get_settings().REDIS_URL)
    await r.flushdb()
    await r.aclose()
asyncio.run(go())
print('reset: redis database 0 cleared (sessions, caches, quotes)')" \
        && SEED_PASSWORDS=random SEED_LOGINS_FILE=/tmp/qa-logins.tsv uv run --frozen python /repo/tools/seed/seed.py \
        && SEED_PASSWORDS=random SEED_LOGINS_FILE=/tmp/qa-logins.tsv uv run --frozen python /repo/tools/seed/demo.py \
        && uv run --frozen python /repo/tools/railway/qa_bucket.py put /tmp/qa-logins.tsv "$KEY"
      rc=$?
    fi ;;
  seed)
    SEED_PASSWORDS=random SEED_LOGINS_FILE=/tmp/qa-logins.tsv uv run --frozen python /repo/tools/seed/seed.py \
      && uv run --frozen python /repo/tools/railway/qa_bucket.py put /tmp/qa-logins.tsv "$KEY"
    rc=$? ;;
  demo)
    uv run --frozen python /repo/tools/railway/qa_bucket.py get "$KEY" /tmp/qa-logins.tsv \
      && SEED_PASSWORDS=random SEED_LOGINS_FILE=/tmp/qa-logins.tsv uv run --frozen python /repo/tools/seed/demo.py \
      && uv run --frozen python /repo/tools/railway/qa_bucket.py put /tmp/qa-logins.tsv "$KEY"
    rc=$? ;;
  checks)
    # each backend's /health over the private network (the worker has no public domain)
    uv run --frozen python -c "
import json, urllib.request
for name, port in (('core-api', 8001), ('realtime', 8004), ('worker', 8006)):
    for path in ('/health', '/health/ready'):
        r = urllib.request.urlopen(f'http://{name}.railway.internal:{port}{path}', timeout=10)
        body = json.loads(r.read())
        print(name, path, r.status, body.get('status'), body.get('environment', ''))" \
      && uv run --frozen alembic current && uv run --frozen alembic heads && uv run --frozen alembic check
    rc=$? ;;
  hours)
    # also clears the OTP send counters, so repeated sign-ins aren't rate limited
    uv run --frozen python -c "
import asyncio
import redis.asyncio as redis
from core_api.integration.conftest import open_all_day
from shared.config import get_settings
from shared.db import engine
async def go():
    await open_all_day(); await engine.dispose()
    r = redis.from_url(get_settings().REDIS_URL)
    n = 0
    async for k in r.scan_iter('otp_attempts:*'):
        await r.delete(k); n += 1
    await r.aclose()
    print('cleared', n, 'OTP counters')
asyncio.run(go())" && echo "opened around the clock"
    rc=$? ;;
  g1|integration)
    # Tests never write to QA or production (tools/target_guard.py): the guard
    # refuses (G1: the QA API's /health says qa; integration: this process is QA's).
    # Kept as a loud refusal so an old runbook step can't write test data.
    if [ "$JOB" = g1 ]; then
      uv run --frozen python /repo/tools/target_guard.py api "${E2E_CORE_API:-}"
    else
      uv run --frozen python /repo/tools/target_guard.py process
    fi
    rc=$?
    if [ $rc -eq 0 ]; then
      echo "$JOB: REFUSED: not run on the QA runner; use make ci (ci-e2e, ci-migrations)"
      rc=3
    fi ;;
  *)
    echo "unknown QA_JOB '$JOB'"; rc=2 ;;
esac
echo "qa-job: $RUN exit=$rc"
exit 0
