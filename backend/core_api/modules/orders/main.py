"""Orders module wiring (was services/order-svc/app/main.py).

CORS, correlation middleware, metrics, health checks, error handlers and the
Redis/DB lifecycle moved to core_api/main.py; orders has no startup work of
its own.
"""
from fastapi import FastAPI

from core_api.modules.orders.api.v1 import orders


def register(app: FastAPI) -> None:
    app.include_router(orders.router, prefix="/api/v1")
