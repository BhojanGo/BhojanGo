"""Alerts (P23): Prometheus rules → Alertmanager → this webhook → the admin
console and the logs. Zero spend: no paging service; ops see firing alerts on
the Operations page and every alert is a log line (Loki) as it fires and ends.

Alertmanager posts its standard webhook body; we keep one row per alert
(fingerprint), so repeats update it rather than piling up.
"""
import hmac
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.support.models import OpsAlert
from shared import authz
from shared.config import get_settings
from shared.db import get_db

router = APIRouter(prefix="/ops/alerts", tags=["Operations"])
logger = structlog.get_logger(__name__)
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("orders.view"))]


class AmAlert(BaseModel):
    status: Literal["firing", "resolved"]
    labels: dict[str, str] = {}
    annotations: dict[str, str] = {}
    startsAt: datetime  # noqa: N815 - Alertmanager's field names
    endsAt: datetime | None = None  # noqa: N815
    fingerprint: str


class AmWebhook(BaseModel):
    """Alertmanager's webhook body (the fields we use)."""

    status: str
    alerts: list[AmAlert]


class OpsAlertOut(BaseModel):
    model_config = {"from_attributes": True}

    name: str
    status: str
    severity: str
    city: str | None
    summary: str
    description: str | None
    starts_at: datetime
    ends_at: datetime | None


def _authorised(authorization: str | None) -> bool:
    token = get_settings().ALERT_WEBHOOK_TOKEN
    given = (authorization or "").removeprefix("Bearer ").strip()
    return bool(token) and hmac.compare_digest(given, token)


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
async def alertmanager_webhook(body: AmWebhook, db: DB, authorization: Annotated[str | None, Header()] = None) -> None:
    if not _authorised(authorization):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Alert webhook")
    from shared import paging

    for a in body.alerts:
        name = a.labels.get("alertname", "alert")
        city = a.labels.get("city") or None
        summary = (a.annotations.get("summary") or name)[:300]
        ends = a.endsAt if a.status == "resolved" and a.endsAt and a.endsAt.year > 1 else None
        values = {"name": name[:80], "status": a.status, "severity": a.labels.get("severity", "warning")[:20], "city": city,
                  "summary": summary, "description": (a.annotations.get("description") or None),
                  "starts_at": a.startsAt, "ends_at": ends, "updated_at": datetime.now(UTC)}
        was = (await db.execute(select(OpsAlert.status).where(OpsAlert.fingerprint == a.fingerprint[:64]))).scalar()
        await db.execute(insert(OpsAlert).values(fingerprint=a.fingerprint[:64], **values)
                         .on_conflict_do_update(index_elements=["fingerprint"], set_=values))
        # R39: a critical alert that starts firing pages whoever is on call (PAGING_WEBHOOK_URL)
        if a.status == "firing" and was != "firing" and values["severity"] in ("critical", "page"):
            await paging.page(summary, values["description"] or "", values["severity"], {"alert": name, "city": city})
        # The log line is the other delivery: it lands in Loki with the service's logs.
        (logger.warning if a.status == "firing" else logger.info)(
            "alert_" + a.status, alert=name, city=city, severity=values["severity"], summary=summary)


class TestAlertOut(BaseModel):
    paging: Literal["sent", "off", "failed"]
    sentry: Literal["sent", "off", "failed"]
    alert: OpsAlertOut


@router.post("/test", response_model=TestAlertOut)
async def send_test_alert(admin: Annotated[AdminContext, Depends(require_permission("admins.grant"))], db: DB) -> TestAlertOut:
    """R39 (admin Settings, "Send test alert"): one alert through every channel that is switched on: the
    Operations page (a TestAlert row, resolved at once), the paging webhook and Sentry. Says which
    channels took it, so an admin can check a newly pasted PAGING_WEBHOOK_URL or SENTRY_DSN."""
    from core_api.modules.support.service.alerts import raise_alert, resolve_alert
    from shared.observability import send_test_event

    admin.require("admins.grant", "*")
    from shared import paging

    now = datetime.now(UTC)
    fp = "test-alert"
    summary = "Test alert from admin Settings: paging works"
    text = f"Sent from admin Settings at {now:%Y-%m-%d %H:%M} UTC. Nothing is wrong."
    await raise_alert(db, fp, "TestAlert", summary, text, severity="critical", now=now)
    paged = await paging.page(summary, text, "critical", {"alert": "TestAlert"})
    sentry = send_test_event(summary)
    await resolve_alert(db, fp, now)
    await db.flush()
    row = (await db.execute(select(OpsAlert).where(OpsAlert.fingerprint == fp))).scalar_one()
    logger.info("test_alert_sent", paging=paged, sentry=sentry)
    return TestAlertOut(paging=paged, sentry=sentry, alert=OpsAlertOut.model_validate(row))  # type: ignore[arg-type]


@router.get("", response_model=list[OpsAlertOut])
async def list_alerts(admin: Viewer, db: DB, scope: str = Query("*", pattern=r"^(\*|[A-Z]{2}(-[A-Z0-9]{1,3}(-[A-Z0-9]{2,5})?)?)$"),
                      state: Literal["firing", "resolved"] = "firing") -> list[OpsAlertOut]:
    """Alerts in your scope: firing ones (the Operations page), or recently resolved.
    Platform-wide ones (error spikes) show to admins who see everywhere."""
    q = select(OpsAlert).where(OpsAlert.status == state).order_by(OpsAlert.starts_at.desc()).limit(100)
    rows = [a for a in (await db.execute(q)).scalars()
            if (a.city is None and admin.can("orders.view", "*")) or
            (a.city is not None and authz.covers(scope, a.city) and admin.can("orders.view", a.city))]
    return [OpsAlertOut.model_validate(a) for a in rows]
