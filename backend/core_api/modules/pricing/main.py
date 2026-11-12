"""Pricing wiring (P8)."""
from fastapi import FastAPI

from core_api.modules.pricing.api.v1 import pricing


def register(app: FastAPI) -> None:
    app.include_router(pricing.router, prefix="/api/v1")
