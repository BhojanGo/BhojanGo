"""Rules and audit wiring (P7)."""
from fastapi import FastAPI

from core_api.modules.rules.api.v1 import commission, rules


def register(app: FastAPI) -> None:
    app.include_router(commission.router, prefix="/api/v1")  # /rules/commission/... before /rules/{rule_id}
    app.include_router(rules.router, prefix="/api/v1")
    app.include_router(rules.audit_router, prefix="/api/v1")
