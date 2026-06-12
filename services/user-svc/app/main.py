import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import addresses, auth, users
from app.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.db.base import engine

configure_logging()
logger = structlog.get_logger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address)
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("user_svc_starting", env=settings.APP_ENV, version=settings.VERSION)
    # Warm up Redis connection
    await get_redis()
    logger.info("user_svc_ready")
    yield
    await close_redis()
    await engine.dispose()
    logger.info("user_svc_stopped")


app = FastAPI(
    title="BhojanGo — User Service",
    description="Authentication, user profiles, and loyalty for BhojanGo",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Correlation ID ───────────────────────────────────────────────────────────
from app.middleware.correlation import CorrelationMiddleware  # noqa: E402

app.add_middleware(CorrelationMiddleware)

# ── Request logging ───────────────────────────────────────────────────────────
from app.middleware.logging import RequestLoggingMiddleware  # noqa: E402

app.add_middleware(RequestLoggingMiddleware)

# ── Prometheus metrics ────────────────────────────────────────────────────────
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app)


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:]) or "body"
        errors.setdefault(field, []).append(error["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": errors,
            },
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("integrity_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "error": {
                "code": "CONFLICT",
                "message": "Resource already exists or constraint violation",
            },
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(addresses.router, prefix="/api/v1")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    checks: dict[str, str] = {}

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"

    return {
        "status": overall,
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

    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

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
