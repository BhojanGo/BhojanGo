# Used by `make test`: runs the checks inside Docker from a copy of the repo, so
# they work the same on Windows, macOS and Linux and never touch host
# node_modules or .venv. Build from the repo root:
#   docker build -f infra/docker/test.Dockerfile --target backend-test .
#   docker build -f infra/docker/test.Dockerfile --target js-test .

# ── Backend: pytest for core_api, realtime and worker ─────────────────────────
FROM python:3.12-slim AS backend-test
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
ENV UV_LINK_MODE=copy \
    DATABASE_URL=postgresql+asyncpg://bhojango:bhojango_test@localhost:5432/bhojango_test \
    JWT_SECRET=test_jwt_secret_for_tests_minimum_32_characters
WORKDIR /srv
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-install-project
COPY backend/ ./
RUN uv run pytest core_api -q && uv run pytest realtime -q && uv run pytest worker -q

# ── JS: turbo test, lint and typecheck for apps and packages ──────────────────
FROM node:24-slim AS js-test
ENV CI=1 NEXT_TELEMETRY_DISABLED=1
WORKDIR /repo
RUN corepack enable
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm turbo build --filter='./packages/*' \
 && pnpm turbo test lint typecheck --filter='./apps/*' --filter='./packages/*'

# ── Migrations: upgrade/downgrade/upgrade, alembic check, seed twice, and the
#    API against the migrated database. Run by `make ci-migrations` through
#    infra/docker/ci.compose.yaml (needs its Postgres and Redis).
FROM python:3.12-slim AS migrations
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/*
ENV UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1
WORKDIR /repo/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-install-project
COPY backend/ ./
COPY tools/ /repo/tools/
COPY infra/docker/db/init.sql /repo/infra/docker/db/init.sql
COPY infra/docker/ci-migrations.sh /repo/ci-migrations.sh
CMD ["sh", "/repo/ci-migrations.sh"]
