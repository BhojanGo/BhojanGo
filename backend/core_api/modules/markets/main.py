"""Markets module wiring (P6)."""
from fastapi import FastAPI

from core_api.modules.markets.api.v1 import markets


def register(app: FastAPI) -> None:
    app.include_router(markets.router, prefix="/api/v1")
