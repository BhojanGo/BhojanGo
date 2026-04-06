import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import delivery, websocket
from app.config import get_settings
from app.core.redis import close_redis, get_redis

logger = structlog.get_logger(__name__)
settings = get_settings()
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("delivery_svc_starting")
    await get_redis()
    logger.info("delivery_svc_ready")
    yield
    await close_redis()
    logger.info("delivery_svc_stopped")


app = FastAPI(
    title="BhojanGo — Delivery Service",
    description="Real-time GPS tracking, WebSockets, and ETA calculation",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)
app.include_router(delivery.router, prefix="/api/v1")
app.include_router(websocket.router)  # WebSocket has no /api/v1 prefix


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    checks: dict[str, str] = {}
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    return {
        "status": "healthy" if all(v == "ok" for v in checks.values()) else "degraded",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "checks": checks,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
