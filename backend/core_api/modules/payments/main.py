"""Payments module wiring (was services/payment-svc/app/main.py).

CORS, correlation middleware, metrics, health checks and the DB lifecycle
moved to core_api/main.py.
"""
from fastapi import FastAPI

from core_api import errors
from core_api.modules.payments.api.v1.payments import router as payments_router
from core_api.modules.payments.api.v1.payments import wallet_router


def register(app: FastAPI) -> None:
    # payment-svc had no IntegrityError or catch-all handler: keep FastAPI's
    # default plain-text 500 for those on payment routes.
    errors.set_style(__package__, errors.ErrorStyle(json_errors=False))

    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(wallet_router, prefix="/api/v1")
