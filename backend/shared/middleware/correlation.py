"""X-Request-ID on every response: the caller's, or a new one. Also the request's
correlation id for events (``request_id_var``, shared/events.py).

R22: pure ASGI. Starlette's BaseHTTPMiddleware ran the app in a separate task with
memory streams on every request (R21 load test: about a tenth of core_api's CPU across
the middlewares built on it).
"""
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class CorrelationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        sent = next((v for k, v in scope["headers"] if k == b"x-request-id"), None)
        req_id = sent.decode("latin-1") if sent is not None else str(uuid.uuid4())
        request_id_var.set(req_id)

        async def with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = req_id
            await send(message)

        await self.app(scope, receive, with_id)
