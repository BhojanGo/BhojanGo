import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import notifications
from shared import bus
from shared.config import get_settings
from shared.db import engine
from app.services import batching
from app.services.outbox_relay import run_relay, stop_relay
from app.services.sqs_consumer import poll_sqs, stop_polling

logger = structlog.get_logger(__name__)
settings = get_settings()
_start_time = time.time()

_sqs_task: asyncio.Task | None = None

# Provider credentials that MUST be present in production — otherwise channels silently no-op
# and customers never receive order confirmations, OTPs, or push updates.
_REQUIRED_PROD_SETTINGS = [
    "SENDGRID_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "FIREBASE_PROJECT_ID",
]


def _validate_production_config() -> None:
    if settings.APP_ENV != "production":
        return
    missing = [name for name in _REQUIRED_PROD_SETTINGS if not getattr(settings.worker, name, "")]
    if not bus.configured():
        missing.append("SQS_QUEUE_URL_NOTIFICATION or EVENT_BUS=redis")
    if missing:
        raise RuntimeError(
            "notification-svc is misconfigured for production; missing required settings: "
            + ", ".join(missing)
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _sqs_task
    logger.info("notification_svc_starting")
    # Fail fast rather than silently mocking notification delivery in production.
    _validate_production_config()
    # Start SQS consumer and the outbox relay (P11) in the background
    _sqs_task = asyncio.create_task(poll_sqs())
    relay_task = None if settings.APP_ENV == "test" else asyncio.create_task(run_relay())
    # Task 43: the batch engine (shadow everywhere; live where a city turns it on)
    batch_task = None if settings.APP_ENV == "test" else asyncio.create_task(batching.run())
    logger.info("notification_svc_ready")
    yield
    stop_polling()
    stop_relay()
    batching.stop()
    for task in (_sqs_task, relay_task, batch_task):
        if task:
            task.cancel()
    await engine.dispose()
    logger.info("notification_svc_stopped")


app = FastAPI(
    title="BhojanGo — Notification Service",
    description="Push, SMS, and email notifications with SQS event consumer",
    version=settings.VERSION,
    lifespan=lifespan,
)

# Security pass: nosniff, CORP, no framing, no referrer on every API response.
from shared.middleware.security import SecurityHeadersMiddleware  # noqa: E402

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)

# P23: traces (OpenTelemetry → collector → Tempo) and the Sentry adapter (off).
from shared import observability  # noqa: E402

from shared.db import engine as _engine  # noqa: E402

observability.setup(app, "worker", sqlalchemy_engine=_engine)
app.include_router(notifications.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    checks["events_configured"] = "ok" if bus.configured() else "not_configured"
    return {
        "status": "healthy" if checks["database"] == "ok" else "degraded",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "checks": checks,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }


@app.get("/health/live", tags=["Health"])
async def liveness() -> dict:
    """Liveness probe — is the process alive?"""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    """Readiness probe — are all dependencies reachable?"""
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    checks["events_configured"] = "ok" if bus.configured() else "not_configured"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "unhealthy",
            "service": settings.SERVICE_NAME,
            "version": settings.VERSION,
            "checks": checks,
        },
    )
