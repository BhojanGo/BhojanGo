#!/bin/sh
# One QA job per deploy of the qa-runner service (infra/railway/qa-runner.Dockerfile),
# chosen by QA_JOB. Runs inside the QA environment's private network, prints a
# result line, and exits (the service's restart policy is NEVER, so it costs
# nothing between jobs). Secrets come from Railway references; nothing secret
# is printed.
#   seed         seed Hyderabad + Boise with random passwords; the logins go to
#                the private uploads bucket (QA_LOGINS_KEY), never to the log
#   checks       migrations at head and `alembic check` against the QA database
#   hours        open the seed cities and restaurants around the clock (for UI tests)
#   g1           G1 against the public QA API (passwords from the bucket)
#   integration  migrations up/down/up, alembic check, seed and the integration
#                suites on a throwaway database (bhojango_it) on QA's Postgres
#                and Redis database 9; the database is dropped afterwards
set -u
cd /repo/backend
RUN="${QA_JOB:-none}"      # <job>#<tag>: the tag tells one run's result from the last one's
JOB="${RUN%%#*}"
KEY="${QA_LOGINS_KEY:-qa-private/seed-logins.tsv}"
echo "qa-job: $RUN (commit ${RAILWAY_GIT_COMMIT_SHA:-local})"
pg_url() { echo "$1" | sed 's/+asyncpg//'; }

case "$JOB" in
  seed)
    SEED_PASSWORDS=random SEED_LOGINS_FILE=/tmp/qa-logins.tsv uv run --frozen python /repo/tools/seed/seed.py \
      && uv run --frozen python /repo/tools/railway/qa_bucket.py put /tmp/qa-logins.tsv "$KEY"
    rc=$? ;;
  checks)
    # each backend's /health over the private network (the worker has no public domain)
    uv run --frozen python -c "
import json, urllib.request
for name, port in (('core-api', 8001), ('realtime', 8004), ('worker', 8006)):
    for path in ('/health', '/health/ready'):
        r = urllib.request.urlopen(f'http://{name}.railway.internal:{port}{path}', timeout=10)
        print(name, path, r.status, json.loads(r.read()).get('status'))" \
      && uv run --frozen alembic current && uv run --frozen alembic heads && uv run --frozen alembic check
    rc=$? ;;
  hours)
    # also clears the OTP send counters, so repeated UI test sign-ins aren't rate limited
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
  g1)
    uv run --frozen python /repo/tools/railway/qa_bucket.py get "$KEY" /tmp/qa-logins.tsv \
      && E2E_LOGINS_FILE=/tmp/qa-logins.tsv E2E_MAILPIT="" uv run --frozen pytest e2e -q --tb=short -p no:cacheprovider
    rc=$? ;;
  integration)
    IT_PSQL="$(pg_url "$IT_DATABASE_URL")"
    ADMIN_PSQL="$(echo "$IT_PSQL" | sed 's#/bhojango_it$#/postgres#')"
    psql "$ADMIN_PSQL" -q -c "DROP DATABASE IF EXISTS bhojango_it" -c "CREATE DATABASE bhojango_it" \
      && env -u APP_ENV -u EVENT_BUS -u EVENT_BUS_REDIS_URL -u RAILWAY_ENVIRONMENT_NAME \
         DATABASE_URL="$IT_DATABASE_URL" REDIS_URL="$IT_REDIS_URL" PSQL_URL="$IT_PSQL" \
         sh /repo/ci-migrations.sh  # the same settings as CI's Migrations job
    rc=$?
    psql "$ADMIN_PSQL" -q -c "DROP DATABASE IF EXISTS bhojango_it WITH (FORCE)" ;;
  *)
    echo "unknown QA_JOB '$JOB'"; rc=2 ;;
esac
echo "qa-job: $RUN exit=$rc"
exit 0
