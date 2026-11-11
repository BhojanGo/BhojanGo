"""Exception handlers for core_api.

The four services merged into core_api did not all format errors the same
way, and error bodies are part of the API contract, so each module registers
the style its old service used and the handler picks the style of the module
that owns the matched route:

* identity (user-svc): validation message "Request validation failed".
* catalog, orders (restaurant-svc, order-svc): "Validation failed".
* payments (payment-svc): "Validation failed", and it had no IntegrityError or
  catch-all handler, so those errors keep FastAPI's default plain-text 500.
"""
from dataclasses import dataclass

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.exc import IntegrityError
from starlette.routing import Match

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ErrorStyle:
    validation_message: str = "Validation failed"
    # True: IntegrityError -> 409 JSON and unhandled errors -> 500 JSON.
    # False: both fall through to FastAPI's default plain-text 500.
    json_errors: bool = True


DEFAULT_STYLE = ErrorStyle()
_styles: dict[str, ErrorStyle] = {}


def set_style(module_package: str, style: ErrorStyle) -> None:
    """Register the error style for routes defined under ``module_package``."""
    _styles[module_package] = style


def _style_for(request: Request) -> ErrorStyle:
    endpoint = request.scope.get("endpoint")
    if endpoint is None:
        for route in request.app.router.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                endpoint = getattr(route, "endpoint", None)
                break
    module = getattr(endpoint, "__module__", "") or ""
    for package, style in _styles.items():
        if module == package or module.startswith(package + "."):
            return style
    return DEFAULT_STYLE


def _plain_500() -> PlainTextResponse:
    return PlainTextResponse("Internal Server Error", status_code=500)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:]) or "body"
        errors.setdefault(field, []).append(error["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": _style_for(request).validation_message,
                "details": errors,
            },
        },
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse | PlainTextResponse:
    if not _style_for(request).json_errors:
        logger.error("unhandled_exception", error=str(exc), path=request.url.path, exc_info=exc)
        return _plain_500()
    logger.warning("integrity_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "error": {
                "code": "CONFLICT",
                "message": "Resource already exists or constraint violation",
            },
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse | PlainTextResponse:
    if not _style_for(request).json_errors:
        return _plain_500()
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        },
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, global_exception_handler)
