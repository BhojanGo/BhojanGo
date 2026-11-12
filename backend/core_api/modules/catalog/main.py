"""Catalog module wiring (was services/restaurant-svc/app/main.py).

CORS, correlation middleware, metrics, health checks, error handlers and the
Redis/DB lifecycle moved to core_api/main.py. What stays here is the
restaurant router and the OpenSearch index bootstrap on startup.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

import asyncio
from datetime import UTC, datetime

from core_api.modules.catalog.api.v1 import menu, restaurants

logger = structlog.get_logger(__name__)


LICENCE_CHECK_SECONDS = 3600


async def _licence_watch() -> None:
    """Every hour: pause Indian listings whose FSSAI licence expired (idempotent,
    so several core_api replicas running it is harmless)."""
    from core_api.modules.catalog.service.menu import pause_expired_licences
    from shared.db import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await pause_expired_licences(db, datetime.now(UTC).date())
                await db.commit()
        except Exception as e:  # noqa: BLE001 - keep watching
            logger.warning("licence_watch_failed", error=str(e))
        await asyncio.sleep(LICENCE_CHECK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from core_api.modules.catalog.service.search import ensure_indices
    from shared.config import get_settings

    try:
        await ensure_indices()
    except Exception as e:
        logger.warning("opensearch_init_failed", error=str(e))
    watch = None if get_settings().APP_ENV == "test" else asyncio.create_task(_licence_watch())
    yield
    if watch:
        watch.cancel()


def register(app: FastAPI) -> None:
    app.state.module_lifespans.append(lifespan)
    # menu first: its fixed paths (/restaurants/licences/check) must win over /restaurants/{id}
    app.include_router(menu.router, prefix="/api/v1")
    app.include_router(restaurants.router, prefix="/api/v1")
