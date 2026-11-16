"""Legal module wiring (R8 F10): Terms and Privacy per country, versions, acceptances."""
from fastapi import FastAPI

from core_api.modules.legal.api.v1 import legal


def register(app: FastAPI) -> None:
    app.include_router(legal.router, prefix="/api/v1")
