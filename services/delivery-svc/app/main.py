import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


@app.get("/health/live", tags=["Health"])
async def liveness() -> dict:
    """Liveness probe — is the process alive?"""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    """Readiness probe — are all dependencies reachable?"""
    checks: dict[str, str] = {}

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

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
