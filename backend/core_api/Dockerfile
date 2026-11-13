# core_api — deployable 1 (identity, catalog, orders, payments).
# Build from backend/:  docker build -f core_api/Dockerfile -t bhojango-core-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/srv/.venv/bin:$PATH" \
    SERVICE_NAME=core-api \
    PORT=8001

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

# Security (trivy): take the base image's pending Debian security fixes.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
WORKDIR /srv

# Dependencies first so code changes don't invalidate the layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY shared shared
COPY core_api core_api
# core_api owns the single migration history; env.py also loads worker's models.
COPY alembic.ini alembic.ini
COPY migrations migrations
COPY worker/app/__init__.py worker/app/__init__.py
COPY worker/app/models worker/app/models

# Security (trivy DS002): run as an unprivileged user, not root.
RUN useradd --system --uid 10001 --no-create-home --home-dir /srv app && mkdir -p /srv/keys && chown app:app /srv/keys
USER app

EXPOSE 8001
# Keep idle connections 130 s (uvicorn's default is 5 s): longer than the load balancer's
# idle timeout (our ALB: 120 s), so it never reuses a connection we just closed (pilot soak).
CMD ["sh", "-c", "alembic upgrade head && uvicorn core_api.main:app --host 0.0.0.0 --port 8001 --timeout-keep-alive 130"]
