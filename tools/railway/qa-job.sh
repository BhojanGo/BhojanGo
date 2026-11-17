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
#                schema (PostGIS re-created), migrations to head, Redis databases 0 and 3
#                cleared, then the base seed and the demo seed with random
#                passwords (logins to the private bucket, QA_LOGINS_KEY). Refused
#                unless RAILWAY_ENVIRONMENT_NAME is QA and APP_ENV is qa.
#   seed         the base seed (Hyderabad + Boise) with random passwords; the
#                logins go to the private uploads bucket, never to the log
#   demo         the demo seed on top of it (tools/seed/demo.py); its logins are
#                added to the same bucket file. Refused unless this is QA (as
#                reset); demo.py itself refuses production before any DB access.
#   checks       read-only: each backend's /health over the private network,
#                migrations at head and `alembic check` against the QA database
#   stripe-e2e   Stripe TEST mode end-to-end (tools/stripe_e2e/run.sh): its own throwaway
#                database on the QA Postgres server (created and dropped by the job),
#                Redis db 11, core-api inside this container, webhooks via the Stripe
#                CLI; never QA's data. Needs STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY
#                (sk_test_ / pk_test_) as sealed variables on qa-runner; without them:
#                "SKIPPED: no Stripe test keys". Live keys refused.
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
# Both names must say QA: Railway's own (any case) and APP_ENV.
is_qa() {
  rw_env="$(printf '%s' "${RAILWAY_ENVIRONMENT_NAME:-}" | tr '[:upper:]' '[:lower:]')"
  [ "$rw_env" = "qa" ] && [ "${APP_ENV:-}" = "qa" ]
}

case "$JOB" in
  reset)
    if ! is_qa; then
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
from urllib.parse import urlsplit, urlunsplit
import redis.asyncio as redis
from shared.config import get_settings
def db(url, n):
    return urlunsplit(urlsplit(url)._replace(path='/' + str(n)))
async def go():
    # 0: core_api and worker (sessions, caches, quotes). 3: realtime (riders, offers, tracking):
    # left alone, its riders stay busy with orders the new database doesn't have.
    for n in (0, 3):
        r = redis.from_url(db(get_settings().REDIS_URL, n))
        await r.flushdb()
        await r.aclose()
asyncio.run(go())
print('reset: redis databases 0 and 3 cleared (sessions, caches, quotes; riders, offers)')" \
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
    if ! is_qa; then
      echo "demo: REFUSED: RAILWAY_ENVIRONMENT_NAME='${RAILWAY_ENVIRONMENT_NAME:-}' APP_ENV='${APP_ENV:-}' (demo data: QA and make dev only)"
      rc=3
    else
      uv run --frozen python /repo/tools/railway/qa_bucket.py get "$KEY" /tmp/qa-logins.tsv \
        && SEED_PASSWORDS=random SEED_LOGINS_FILE=/tmp/qa-logins.tsv uv run --frozen python /repo/tools/seed/demo.py \
        && uv run --frozen python /repo/tools/railway/qa_bucket.py put /tmp/qa-logins.tsv "$KEY"
      rc=$?
    fi ;;
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
    # Removed: it rewrote QA's opening hours for tests. Tests never write to QA;
    # the demo seed's hours are what QA shows.
    echo "qa-job: 'hours' was removed (tests never write to QA)"; rc=3 ;;
  stripe-e2e)
    sh /repo/tools/stripe_e2e/run.sh
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
