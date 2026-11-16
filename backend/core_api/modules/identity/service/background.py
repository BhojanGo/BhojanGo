"""Fire-and-forget work that must not change how long a response takes.

Sign-in answers must not reveal whether an account exists, also not by timing:
sending an email or writing an audit row only for real accounts would make
those answers slower. Such work is spawned here and finishes after the answer.
Tests call ``drain()`` to wait for it.
"""
import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)
_tasks: set[asyncio.Task] = set()


async def _guarded(coro: Coroutine[Any, Any, Any], name: str) -> None:
    try:
        await coro
    except Exception as e:  # noqa: BLE001 - background work never breaks a request
        logger.error("background_task_failed", task=name, error=str(e))


def spawn(coro: Coroutine[Any, Any, Any], name: str = "") -> None:
    task = asyncio.get_running_loop().create_task(_guarded(coro, name or "task"))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait until every spawned task has finished (tests, shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
