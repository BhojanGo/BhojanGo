# realtime — deployable 2 (rider GPS, tracking WebSocket, ETA). Was delivery-svc.
# Build from backend/:  docker build -f realtime/Dockerfile -t bhojango-realtime .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/srv/.venv/bin:$PATH" \
    SERVICE_NAME=delivery-svc \
    PORT=8004 \
    REDIS_URL=redis://localhost:6379/3

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

# Security (trivy): take the base image's pending Debian security fixes.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
WORKDIR /srv

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY shared shared
COPY realtime/app app

# Security (trivy DS002): run as an unprivileged user, not root.
RUN useradd --system --uid 10001 --no-create-home --home-dir /srv app && mkdir -p /srv/keys && chown app:app /srv/keys
USER app

EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
