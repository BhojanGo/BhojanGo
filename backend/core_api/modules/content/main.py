"""Content module wiring (round 8): admin-managed content for the website.
Help centre (F9); Legal joins it (F10)."""
from fastapi import FastAPI

from core_api.modules.content.api.v1 import help_admin, help_public


def register(app: FastAPI) -> None:
    app.include_router(help_public.router, prefix="/api/v1")
    app.include_router(help_admin.router, prefix="/api/v1")
