"""Incident tools module wiring (R17)."""
from fastapi import FastAPI

from core_api.modules.incidents.api.v1 import incidents


def register(app: FastAPI) -> None:
    app.include_router(incidents.router, prefix="/api/v1")
