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
