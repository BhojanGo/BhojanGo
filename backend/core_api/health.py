"""Health endpoints — one shared copy for core_api.

identity, catalog and orders each exposed identical /health, /health/live and
/health/ready endpoints (payments checked only the database). They are now a
single set that checks Redis and the database and reports the core_api
SERVICE_NAME.
"""
import time
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from shared.config import get_settings
from shared.db import engine
from shared.redis import get_redis

settings = get_settings()
router = APIRouter(tags=["Health"])
_start_time = time.time()


async def _check(detail: bool) -> dict[str, str]:
    checks: dict[str, str] = {}

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}" if detail else "error"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}" if detail else "error"

    return checks


@router.get("/health")
async def health_check() -> dict:
    checks = await _check(detail=False)
    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": overall,
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe — is the process alive?"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Readiness probe — are all dependencies reachable?"""
    checks = await _check(detail=True)
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
