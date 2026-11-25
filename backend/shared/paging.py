"""R39: page whoever is on call through one webhook (``PAGING_WEBHOOK_URL``).

One JSON POST that the usual receivers read as they are: ``text`` (Slack, Mattermost, Google Chat),
``content`` (Discord), ``title``/``message``/``priority`` (ntfy JSON, Opsgenie-style), plus the alert's
fields. Never raises: paging must not break what raised the alert. Returns what happened:
"sent", "off" (no URL set) or "failed" (logged, with the HTTP status or error).
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from shared.config import get_settings

logger = structlog.get_logger(__name__)
SEVERITY_PRIORITY = {"critical": 5, "page": 5, "warning": 3, "info": 2}


def body(title: str, text: str, severity: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    s = get_settings()
    env = getattr(s, "environment_name", None) or s.APP_ENV
    line = f"[{severity.upper()}] {title}" + (f" ({env})" if env else "")
    return {"text": f"{line}\n{text}".strip(), "content": f"{line}\n{text}".strip()[:1900], "title": line,
            "message": text or title, "priority": SEVERITY_PRIORITY.get(severity, 3), "severity": severity,
            "environment": env, "source": "bhojango", "details": details or {}}


async def page(title: str, text: str = "", severity: str = "critical", details: dict[str, Any] | None = None) -> str:
    s = get_settings()
    url = (s.PAGING_WEBHOOK_URL or "").strip()
    if not url:
        logger.info("page_skipped_no_webhook", title=title, severity=severity)
        return "off"
    try:
        async with httpx.AsyncClient(timeout=s.PAGING_TIMEOUT_SECONDS) as client:
            r = await client.post(url, json=body(title, text, severity, details))
        if r.status_code >= 300:
            logger.error("page_failed", title=title, status=r.status_code)
            return "failed"
    except httpx.HTTPError as e:
        logger.error("page_failed", title=title, error=type(e).__name__)
        return "failed"
    logger.warning("page_sent", title=title, severity=severity)
    return "sent"
