import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import notifications
from app.config import get_settings
from app.db.base import engine
from app.services.sqs_consumer import poll_sqs, stop_polling

logger = structlog.get_logger(__name__)
settings = get_settings()
_start_time = time.time()

_sqs_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _sqs_task
    logger.info("notification_svc_starting")
    # Start SQS consumer in background
    _sqs_task = asyncio.create_task(poll_sqs())
    logger.info("notification_svc_ready")
    yield
    stop_polling()
    if _sqs_task:
        _sqs_task.cancel()
    await engine.dispose()
    logger.info("notification_svc_stopped")


app = FastAPI(
    title="BhojanGo — Notification Service",
    description="Push, SMS, and email notifications with SQS event consumer",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)
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
    sqs_ok = bool(settings.SQS_QUEUE_URL_NOTIFICATION)
    checks["sqs_configured"] = "ok" if sqs_ok else "not_configured"
    return {
        "status": "healthy" if checks["database"] == "ok" else "degraded",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "checks": checks,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
