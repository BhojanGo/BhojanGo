"""Orders module wiring.

Besides the routes, core_api runs the order timeout sweeper (P11): every few
seconds it cancels unpaid orders past their payment deadline and paid orders
the restaurant didn't accept in time (refunded). Rows are claimed with
SKIP LOCKED, so running it in every core_api replica is safe.
"""
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from core_api.modules.orders.api.v1 import internal, orders

logger = structlog.get_logger(__name__)
SWEEP_SECONDS = 10


async def _sweep_forever() -> None:
    from core_api.modules.orders.service.order import OrderService
    from shared.db import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await OrderService(db).sweep()
                await db.commit()
        except Exception as e:  # noqa: BLE001 - keep sweeping
            logger.warning("order_sweep_failed", error=str(e))
        await asyncio.sleep(SWEEP_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from shared.config import get_settings

    task = None if get_settings().APP_ENV == "test" else asyncio.create_task(_sweep_forever())
    yield
    if task:
        task.cancel()


def register(app: FastAPI) -> None:
    app.state.module_lifespans.append(lifespan)
    app.include_router(orders.router, prefix="/api/v1")
    app.include_router(internal.router, prefix="/api/v1")
