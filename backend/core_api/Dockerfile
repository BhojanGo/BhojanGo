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
# R19: the store review accounts, run once in production at go-live (`python tools/review_accounts.py`).
COPY tools/review_accounts.py tools/review_accounts.py

# Optional: the website's "near you" hint from the visitor's IP (shared/geoip.py), from
# DB-IP's free City Lite database (CC BY 4.0). GEOIP=1 fetches it at build time; without
# it (or if the download fails) the hint is simply off.
ARG GEOIP=0
ENV GEOIP_DB_PATH=/srv/geoip/dbip-city-lite.mmdb
COPY tools/geoip_fetch.py tools/geoip_fetch.py
RUN if [ "$GEOIP" = "1" ]; then python tools/geoip_fetch.py "$GEOIP_DB_PATH"; fi

# Security (trivy DS002): run as an unprivileged user, not root.
RUN useradd --system --uid 10001 --no-create-home --home-dir /srv app && mkdir -p /srv/keys && chown app:app /srv/keys
USER app

EXPOSE 8001
# R22: core_api/start.sh runs one uvicorn process per CPU the container may use (at most
# WEB_CONCURRENCY_MAX, default 2; WEB_CONCURRENCY overrides), keep-alive 130 s.
CMD ["sh", "-c", "alembic upgrade head && exec sh core_api/start.sh"]
