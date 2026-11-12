"""Support module wiring (B3, B5): tickets for the admin support console."""
from fastapi import FastAPI

from core_api.modules.support.api.v1 import tickets


def register(app: FastAPI) -> None:
    app.include_router(tickets.router, prefix="/api/v1")
