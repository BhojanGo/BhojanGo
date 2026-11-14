# QA jobs inside Railway's private network: seeding, migration checks, G1 and
# the integration suite (docs/runbooks/railway-deploy.md, "Test QA").
# Not part of .railway/railway.ts: a temporary service, deployed with
# `railway up` from a staged copy (tools/railway/qa-runner.sh) and deleted after.
# Postgres and Redis stay private; the job reaches them as the services do.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/*
ENV UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /repo/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-install-project
COPY backend/ ./
COPY tools/ /repo/tools/
COPY packages/api-client/openapi /repo/packages/api-client/openapi
COPY infra/docker/db/init.sql /repo/infra/docker/db/init.sql
COPY infra/docker/ci-migrations.sh /repo/ci-migrations.sh
CMD ["sh", "/repo/tools/railway/qa-job.sh"]
