"""One log line when a request starts and one when its response starts (status and
duration), plus X-Response-Time. R22: pure ASGI (it was a BaseHTTPMiddleware: a task
and memory streams per request)."""
import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shared.client_ip import client_ip

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        request = Request(scope)
        # Attach request_id for downstream use (request.state.request_id)
        request.state.request_id = request_id
        log = logger.bind(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip(request),
        )
        log.info("request_started")

        async def logged(message: Message) -> None:
            if message["type"] == "http.response.start":
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                log.info("request_completed", status_code=message["status"], duration_ms=duration_ms)
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id  # the correlation middleware (outside) sets the final one
                headers["X-Response-Time"] = f"{duration_ms}ms"
            await send(message)

        try:
            await self.app(scope, receive, logged)
        except Exception as exc:
            log.exception("request_failed", error=str(exc))
            raise
