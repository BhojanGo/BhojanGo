"""R39: an Operations alert raised by the code (not by Prometheus): one row per fingerprint, shown on
the admin Operations page while it fires, logged, and paged (shared/paging.py) when it is new and
``page`` is set. Alertmanager's own alerts arrive through api/v1/alerts.py and page the same way."""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.support.models import OpsAlert
from shared import paging

logger = structlog.get_logger(__name__)


async def raise_alert(db: AsyncSession, fingerprint: str, name: str, summary: str, description: str | None = None,
                      severity: str = "warning", city: str | None = None, page: bool = False,
                      now: datetime | None = None) -> str | None:
    """Fire (or refresh) an alert. Returns the paging result ("sent", "off", "failed") when it paged."""
    now = now or datetime.now(UTC)
    values = {"name": name[:80], "status": "firing", "severity": severity[:20], "city": city,
              "summary": summary[:300], "description": (description or None) and description[:1000],
              "starts_at": now, "ends_at": None, "updated_at": now}
    fp = fingerprint[:64]
    was = (await db.execute(select(OpsAlert.status).where(OpsAlert.fingerprint == fp))).scalar()
    await db.execute(insert(OpsAlert).values(fingerprint=fp, **values)
                     .on_conflict_do_update(index_elements=["fingerprint"], set_=values))
    logger.warning("alert_firing", alert=name, city=city, severity=severity, summary=summary)
    if page and was != "firing":
        return await paging.page(summary, description or "", severity, {"alert": name, "city": city})
    return None


async def resolve_alert(db: AsyncSession, fingerprint: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    await db.execute(update(OpsAlert).where(OpsAlert.fingerprint == fingerprint[:64], OpsAlert.status == "firing")
                     .values(status="resolved", ends_at=now, updated_at=now))
