#!/bin/sh
# Same steps as the "Migrations" job in .github/workflows/backend-checks.yml.
set -eu
cd /repo/backend
echo "== schemas and extensions"
psql "$PSQL_URL" -q -f /repo/infra/docker/db/init.sql
echo "== alembic upgrade, downgrade, upgrade"
uv run --frozen alembic upgrade head
uv run --frozen alembic downgrade base
uv run --frozen alembic upgrade head
echo "== alembic check (models match migrations)"
uv run --frozen alembic check
echo "== markets-only seed on a fresh database, as production (R19)"
psql "$PSQL_URL" -v ON_ERROR_STOP=1 -q -c "DROP DATABASE IF EXISTS bhojango_markets" -c "CREATE DATABASE bhojango_markets"
psql "${PSQL_URL%/*}/bhojango_markets" -v ON_ERROR_STOP=1 -q -f /repo/infra/docker/db/init.sql
(
  export DATABASE_URL="${DATABASE_URL%/*}/bhojango_markets"
  uv run --frozen alembic upgrade head
  for run in 1 2; do
    APP_ENV=production PAYMENT_PROVIDER=live PAYOUT_PROVIDER=live OTP_FIXED_CODE= DELIVERY_PIN_FIXED= \
      uv run --frozen python ../tools/seed/markets.py
  done
  if APP_ENV=production uv run --frozen python ../tools/seed/seed.py; then echo "the full seed ran in production"; exit 1; fi
  RUN_MARKETS_ONLY_DB_TESTS=1 uv run --frozen pytest core_api/integration/test_markets_only_seed.py -q --tb=short
)
echo "== seed twice (must be idempotent)"
uv run --frozen python ../tools/seed/seed.py >/dev/null
uv run --frozen python ../tools/seed/seed.py
echo "== API on the migrated database"
RUN_MIGRATED_DB_TESTS=1 uv run --frozen pytest core_api/integration -q --tb=short
echo "== worker messages on the migrated database"
RUN_MIGRATED_DB_TESTS=1 uv run --frozen pytest worker/tests/integration -q --tb=short
echo "== API contract: the generated client matches the OpenAPI documents"
uv run --frozen python tools/dump_openapi.py --check
echo "== migrations OK"
