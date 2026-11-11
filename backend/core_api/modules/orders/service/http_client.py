"""Resilient HTTP client for inter-service communication."""

import structlog
from httpx import AsyncClient, Timeout
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

SERVICE_TIMEOUT = Timeout(connect=3.0, read=8.0, write=5.0, pool=5.0)


def create_service_client(**kwargs) -> AsyncClient:
    """Create an httpx AsyncClient with sensible defaults."""
    return AsyncClient(timeout=SERVICE_TIMEOUT, **kwargs)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
async def resilient_get(client: AsyncClient, url: str, **kwargs):
    """GET with retry and exponential backoff."""
    logger.debug("service_call", method="GET", url=url)
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return response


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
async def resilient_post(client: AsyncClient, url: str, **kwargs):
    """POST with retry and exponential backoff."""
    logger.debug("service_call", method="POST", url=url)
    response = await client.post(url, **kwargs)
    response.raise_for_status()
    return response
