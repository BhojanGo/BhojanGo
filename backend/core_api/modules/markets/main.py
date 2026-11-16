"""Markets module wiring (P6)."""
from fastapi import FastAPI

from core_api.modules.markets.api.v1 import delivery, markets, public


def register(app: FastAPI) -> None:
    app.include_router(public.router, prefix="/api/v1")
    app.include_router(markets.router, prefix="/api/v1")
    app.include_router(delivery.router, prefix="/api/v1")
