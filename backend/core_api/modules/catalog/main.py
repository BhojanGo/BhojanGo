"""Catalog module wiring (was services/restaurant-svc/app/main.py).

CORS, correlation middleware, metrics, health checks, error handlers and the
Redis/DB lifecycle moved to core_api/main.py. What stays here is the
restaurant router and the OpenSearch index bootstrap on startup.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from core_api.modules.catalog.api.v1 import restaurants

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from core_api.modules.catalog.service.search import ensure_indices

    try:
        await ensure_indices()
    except Exception as e:
        logger.warning("opensearch_init_failed", error=str(e))
    yield


def register(app: FastAPI) -> None:
    app.state.module_lifespans.append(lifespan)
    app.include_router(restaurants.router, prefix="/api/v1")
