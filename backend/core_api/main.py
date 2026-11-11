"""core_api — deployable 1. One FastAPI app for identity, catalog, orders and
payments (previously user-svc, restaurant-svc, order-svc and payment-svc).

Every module keeps the URL prefixes it had as a separate service. Each module's
old main.py is now a ``register(app)`` function that adds its routers and any
module-specific middleware, error style or startup/shutdown hook.

Run: ``uvicorn core_api.main:app --port 8001`` from backend/.
"""
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from core_api import errors, health
from core_api.modules.catalog.main import register as register_catalog
from core_api.modules.identity.main import register as register_identity
from core_api.modules.orders.main import register as register_orders
from shared.config import get_settings
from shared.db import engine
from shared.logging import configure_logging
from shared.middleware.correlation import CorrelationMiddleware
from shared.middleware.logging import RequestLoggingMiddleware
from shared.redis import close_redis, get_redis

configure_logging()
logger = structlog.get_logger(__name__)
settings = get_settings()

MODULES = [
    register_identity,
    register_catalog,
    register_orders,
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("core_api_starting", env=settings.APP_ENV, version=settings.VERSION)
    # Warm up Redis connection
    await get_redis()
    async with AsyncExitStack() as stack:
        for module_lifespan in app.state.module_lifespans:
            await stack.enter_async_context(module_lifespan(app))
        logger.info("core_api_ready")
        yield
    await close_redis()
    await engine.dispose()
    logger.info("core_api_stopped")


app = FastAPI(
    title="BhojanGo — Core API",
    description="Identity, catalog, orders and payments for BhojanGo",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
# Modules append async context managers (app) -> lifespan for startup/shutdown work.
app.state.module_lifespans = []

for register in MODULES:
    register(app)

# ── Shared middleware (last added runs first) ─────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
# Outermost, so X-Request-ID echoes the caller's id (or a new one) on every route.
app.add_middleware(CorrelationMiddleware)

# ── Prometheus metrics ────────────────────────────────────────────────────────
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app)

errors.install(app)
app.include_router(health.router)
