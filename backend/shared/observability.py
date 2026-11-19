"""Observability (P23), zero spend: OpenTelemetry traces to a local collector
(→ Tempo, seen in Grafana: `make observe`), and Sentry error reporting (R19:
the free plan) that stays off until SENTRY_DSN is set.

- Traces: on when OTEL_EXPORTER_OTLP_ENDPOINT is set (the observe overlay sets
  it to the collector). FastAPI requests, SQLAlchemy queries and outgoing httpx
  calls become spans; log lines carry the trace id so Grafana links Loki → Tempo.
- Metrics: every service already exposes Prometheus /metrics; core_api adds the
  pilot KPIs (core_api/modules/orders/service/kpi.py).
- Errors: with SENTRY_DSN set, sentry-sdk (a dependency since R19) reports
  unhandled errors and report_error() calls. No DSN (dev, CI, QA): no init and
  no network; errors are in the logs and the error-spike alert.
"""
from typing import Any

import structlog
from fastapi import FastAPI

from shared.config import get_settings

logger = structlog.get_logger(__name__)
_sentry_on = False


def setup(app: FastAPI, service: str, *, sqlalchemy_engine: Any = None) -> None:
    _tracing(app, service, sqlalchemy_engine)
    _sentry(service)


def _tracing(app: FastAPI, service: str, engine: Any) -> bool:
    s = get_settings()
    endpoint = s.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
    if not endpoint:
        return False
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({
        "service.name": service, "service.version": s.VERSION, "deployment.environment": s.APP_ENV}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
    HTTPXClientInstrumentor().instrument()
    if engine is not None:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    logger.info("tracing_on", service=service, endpoint=endpoint)
    return True


def _sentry(service: str) -> None:
    """The Sentry adapter: off unless SENTRY_DSN is set (and sentry-sdk installed)."""
    global _sentry_on
    s = get_settings()
    if not s.SENTRY_DSN:
        return
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("sentry_dsn_set_but_sdk_missing", service=service)
        return
    # Errors only (no tracing, no request bodies or personal data). A malformed DSN is logged, never fatal.
    try:
        sentry_sdk.init(dsn=s.SENTRY_DSN, environment=s.environment_name, release=s.VERSION, server_name=service,
                        traces_sample_rate=0.0, send_default_pii=False, max_request_body_size="never")
    except Exception as e:  # noqa: BLE001 - sentry_sdk's BadDsn and friends
        logger.warning("sentry_init_failed", service=service, error=type(e).__name__)
        return
    sentry_sdk.set_tag("service", service)
    _sentry_on = True


def report_error(exc: BaseException, **context: Any) -> None:
    """Report an unexpected error: always logged; also to Sentry when the adapter is on."""
    logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__, **context)
    if _sentry_on:
        import sentry_sdk  # type: ignore[import-not-found]

        sentry_sdk.capture_exception(exc)


def add_trace_id(_: Any, __: str, event: dict) -> dict:
    """structlog processor: the current trace id, so a log line links to its trace."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            event["trace_id"] = format(ctx.trace_id, "032x")
    except Exception:  # noqa: BLE001 - logging must never fail
        pass
    return event
