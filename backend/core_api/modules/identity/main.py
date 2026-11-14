"""Identity module wiring (was services/user-svc/app/main.py).

Moved into core_api: CORS, correlation/request logging middleware, Prometheus
metrics, health checks and the Redis/DB lifecycle now live in core_api/main.py
and are shared by every module.
"""
from fastapi import FastAPI
from shared.client_ip import client_ip
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core_api import errors
from core_api.modules.identity.api.v1 import addresses, admin, auth, riders, signup, users
from shared import jwt_keys


def register(app: FastAPI) -> None:
    # ── Rate limiting (auth endpoints use @limiter.limit) ─────────────────────
    app.state.limiter = Limiter(key_func=client_ip)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # user-svc worded its validation error differently from the other services.
    errors.set_style(__package__, errors.ErrorStyle(validation_message="Request validation failed"))

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(addresses.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(riders.router, prefix="/api/v1")
    app.include_router(riders.internal, prefix="/api/v1")
    app.include_router(signup.router, prefix="/api/v1")

    # Public keys for verifying our RS256 tokens (realtime and worker use it).
    @app.get("/.well-known/jwks.json", tags=["Authentication"], include_in_schema=True)
    async def jwks() -> dict:
        return jwt_keys.jwks()

    # Fail at start-up, not on the first sign-in, if the signing key is missing.
    jwt_keys.signing_key()
