"""Security headers on every API response (security pass: OWASP ZAP flagged
missing X-Content-Type-Options and Cross-Origin-Resource-Policy, Low).

Pure ASGI, so it costs nothing on WebSockets and streaming responses.
"""
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    # The apps call the API from another origin of the same site (bhojango.com → api.bhojango.com).
    (b"cross-origin-resource-policy", b"same-site"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {k.lower() for k, _ in message.get("headers", [])}
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(k, v) for k, v in HEADERS if k not in present]
            await send(message)

        await self.app(scope, receive, with_headers)
