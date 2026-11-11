# worker — deployable 3 (notifications HTTP API + SQS consumer). Was notification-svc.
# Migrations run from core_api; this image does not run them.
# Build from backend/:  docker build -f worker/Dockerfile -t bhojango-worker .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/srv/.venv/bin:$PATH" \
    SERVICE_NAME=notification-svc \
    PORT=8006 \
    DB_POOL_SIZE=5

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /srv

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY shared shared
COPY worker/app app

EXPOSE 8006
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
