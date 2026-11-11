"""
Notification dispatcher — routes events to the right channels.
Called by the SQS consumer and the REST API.
"""
import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import DeviceToken, Notification
from app.services import email as email_svc
from app.services import fcm, sms
from app.services.templates import get_template

logger = structlog.get_logger(__name__)

# Map SNS event_type → notification template key
EVENT_TO_TEMPLATE = {
    "order.created": "order_created",
    "order.confirmed": "order_confirmed",
    "order.status_changed": None,          # handled by status below
    "order.cancelled": "order_cancelled",
    "payment.succeeded": "payment_succeeded",
    "payment.failed": "payment_failed",
    "driver.assigned": "driver_assigned",
}

STATUS_TO_TEMPLATE = {
    "preparing": "order_preparing",
    "ready_for_pickup": "order_ready",
    "picked_up": "order_picked_up",
    "delivered": "order_delivered",
}


async def dispatch_event(
    event: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Main entry point. Receive a parsed domain event, dispatch notifications."""
    event_type = event.get("event_type", "")
    payload = event.get("payload", {})

    template_key = EVENT_TO_TEMPLATE.get(event_type)
    if event_type == "order.status_changed":
        template_key = STATUS_TO_TEMPLATE.get(payload.get("new_status", ""))

    if not template_key:
        logger.debug("no_template_for_event", event_type=event_type)
        return

    user_id_str = payload.get("customer_id") or payload.get("user_id")
    if not user_id_str:
        logger.warning("no_user_id_in_event", event_type=event_type)
        return

    # Build template params
    template_params: dict[str, str] = {
        "order_id": payload.get("order_id", "")[:8].upper() if payload.get("order_id") else "",
        "restaurant_name": payload.get("restaurant_name", "the restaurant"),
        "driver_name": payload.get("driver_name", "your driver"),
        "eta": payload.get("eta", "soon"),
        "amount": str(payload.get("amount", "")),
        "currency": payload.get("currency", "USD"),
    }

    # Default to en-US locale (in production: fetch from user-svc)
    locale = "en-US"
    title, body = get_template(template_key, locale, **template_params)

    # Save in-app notification
    notif = Notification(
        user_id=uuid.UUID(user_id_str),
        type=template_key,
        channel="in_app",
        title=title,
        body=body,
        data={"event_type": event_type, "order_id": payload.get("order_id", "")},
        sent_at=datetime.now(UTC),
    )
    db.add(notif)
    await db.flush()

    # Get user FCM tokens
    from sqlalchemy import select
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.user_id == uuid.UUID(user_id_str))
    )
    tokens = result.scalars().all()

    if tokens:
        token_strings = [t.token for t in tokens]
        push_data = {"event_type": event_type, "order_id": payload.get("order_id", "")}
        await fcm.send_multicast(token_strings, title, body, push_data)
        logger.info("push_sent", user_id=user_id_str, count=len(token_strings))

    logger.info("notification_dispatched", event_type=event_type, user_id=user_id_str, template=template_key)
