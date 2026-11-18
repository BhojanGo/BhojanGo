"""Finance wiring (P13). An hourly job drafts last week's payout run for each
live country on its payout day (business rule payout_schedule); a second
finance admin still approves and pays it. On that day it also pays again any
statement that was reversed or failed."""
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from core_api.modules.finance.api.v1 import finance

logger = structlog.get_logger(__name__)
CHECK_SECONDS = 3600


async def _weekly_drafts() -> None:
    from core_api.modules.finance.service.schedule import ensure_weekly_drafts, repay_unpaid
    from shared.db import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await ensure_weekly_drafts(db)
                await db.commit()
            async with AsyncSessionLocal() as db:
                await repay_unpaid(db)  # payout day: what was sent back or failed is paid again
                await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("payout_draft_failed", error=str(e))
        await asyncio.sleep(CHECK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from shared.config import get_settings

    task = None if get_settings().APP_ENV == "test" else asyncio.create_task(_weekly_drafts())
    yield
    if task:
        task.cancel()


def register(app: FastAPI) -> None:
    app.state.module_lifespans.append(lifespan)
    app.include_router(finance.router, prefix="/api/v1")
