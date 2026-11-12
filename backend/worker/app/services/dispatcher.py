"""Domain events → messages (P15).

Outbox events arrive from SNS → SQS. Each one becomes messages for the people
it concerns (customer, restaurant owner, payee), in their language (en, hi,
te from preferred_locale), on the channels in POLICY:

- push to every device the person has (Expo, FCM or APNs);
- SMS only where it matters and the person has no device to push to
  (``sms_fallback``): rider on the way, cancellations, failed payments, a new
  order for a restaurant without the tablet app. SMS costs money per message;
- email for things worth keeping: order confirmation, receipt, cancellation
  and refunds, payouts;
- always an in-app notification (the app's inbox).

Every message is recorded once per event, person and channel, so a redelivered
event never sends twice.
"""
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.services import messages as m
from app.services.directory import Directory, Person
from shared import notify
from shared.providers.email import EmailProvider, get_email_provider
from shared.providers.push import PushMessage, PushProvider, get_push_provider
from shared.providers.sms import get_sms_provider

logger = structlog.get_logger(__name__)

POLICY: dict[str, tuple[str, ...]] = {
    "order_placed": ("push", "email"),
    "order_accepted": ("push",),
    "order_preparing": ("push",),
    "driver_assigned": ("push",),
    "order_picked_up": ("push", "sms_fallback"),
    "order_delivered": ("push", "email"),
    "order_cancelled_refunded": ("push", "email", "sms_fallback"),
    "order_cancelled_unpaid": ("push", "sms_fallback"),
    "payment_failed": ("push", "sms_fallback"),
    "refund_items": ("push", "email"),
    "partner_new_order": ("push", "sms_fallback"),
    "payout_paid": ("push", "email"),
}
STATUS_MESSAGES = {"accepted": "order_accepted", "preparing": "order_preparing",
                   "picked_up": "order_picked_up", "delivered": "order_delivered"}
RECEIPTS = {"order_placed", "order_delivered", "order_cancelled_refunded", "refund_items"}


@dataclass
class Outgoing:
    user_id: str
    key: str
    params: dict[str, Any]
    order_id: str | None = None
    total: str | None = None  # shown in emails
    data: dict[str, str] = field(default_factory=dict)


async def plan(event: dict, d: Directory) -> list[Outgoing]:
    """Who gets which message for this event."""
    kind, p = event.get("event_type", ""), event.get("payload", {})
    order_id = p.get("order_id")
    order = await d.order(order_id) if order_id else None

    if kind == "payout.paid":
        user = p.get("user_id") or (await d.restaurant_owner(p["payee_id"]) if p.get("payee_type") == "restaurant"
                                    else p.get("payee_id"))
        if not user:
            return []
        span = await d.payout_period(p["run_id"]) if p.get("run_id") else None
        return [Outgoing(str(user), "payout_paid", {"amount": m.money(Decimal(str(p["amount"])), p["currency"]),
                                                     "period": m.period(*span) if span else ""},
                         data={"statement_id": p.get("statement_id", "")})]
    if order is None:
        return []

    tz = await d.timezone(order["market_city"])
    code = m.order_code(str(order["id"]))
    total = m.money(order["total"], order["currency"])
    eta = m.clock(p.get("estimated_delivery_time") or order["estimated_delivery_time"], tz)
    base = {"restaurant": order["restaurant_name"], "code": code, "eta": eta}
    customer = str(order["customer_id"])

    def to_customer(key: str, **extra: Any) -> Outgoing:
        return Outgoing(customer, key, {**base, **extra}, str(order["id"]), total if key in RECEIPTS else None)

    if kind == "order.placed":
        out = [to_customer("order_placed")]
        owner = await d.restaurant_owner(str(order["restaurant_id"]))
        if owner:
            items = sum(int(i.get("quantity", 1)) for i in (order["items"] or []))
            out.append(Outgoing(str(owner), "partner_new_order",
                                {"code": code, "items": items, "total": total,
                                 "accept_by": m.clock(order["accept_due_at"], tz) or ""}, str(order["id"])))
        return out
    if kind == "order.status_changed":
        key = STATUS_MESSAGES.get(p.get("new_status", ""))
        if key == "order_picked_up":
            rider = await d.person(order["driver_id"]) if order["driver_id"] else None
            return [to_customer(key, rider=rider.first_name if rider else "Your rider")]
        return [to_customer(key)] if key else []
    if kind == "driver.assigned":
        name = (p.get("driver_name") or "").split(" ")[0] or "Your rider"
        return [to_customer("driver_assigned", rider=name)]
    if kind == "order.cancelled":
        refund = int(p.get("refund_amount") or 0)
        if refund:
            return [to_customer("order_cancelled_refunded", refund=m.minor_to_money(refund, order["currency"]))]
        return [to_customer("order_cancelled_unpaid")]
    if kind == "payment.failed":
        return [to_customer("payment_failed")]
    if kind == "payment.refunded" and p.get("items"):  # full refunds are told with the cancellation
        return [to_customer("refund_items", amount=m.minor_to_money(p["amount"], p["currency"]))]
    return []


class Sender:
    """Delivers planned messages and records each one (once per event, person, channel)."""

    def __init__(self, db: AsyncSession, directory: Directory | None = None, push: PushProvider | None = None,
                 email: EmailProvider | None = None) -> None:
        self.db, self.d = db, directory or Directory(db)
        self.push = push or get_push_provider()
        self.email = email or get_email_provider()

    async def _claim(self, event_id: str, person: Person, r: m.Rendered, channel: str, data: dict) -> uuid.UUID | None:
        """Record the message before sending it; None = already sent for this event."""
        row = (await self.db.execute(insert(Notification).values(
            id=uuid.uuid4(), user_id=person.id, type=r.key, channel=channel, title=r.title, body=r.body,
            data=data, event_id=event_id, language=r.language, status="sending",
        ).on_conflict_do_nothing(index_elements=["event_id", "user_id", "channel"],
                                 index_where=Notification.event_id.isnot(None)).returning(Notification.id))).scalar()
        return row

    async def _done(self, nid: uuid.UUID, ok: bool) -> None:
        n = await self.db.get(Notification, nid)
        if n is not None:
            n.status, n.sent_at = ("sent" if ok else "failed"), datetime.now(UTC)

    async def deliver(self, event_id: str, out: Outgoing) -> dict[str, str]:
        person = await self.d.person(out.user_id)
        if person is None:
            return {}
        r = m.render(out.key, m.language_for(person.locale), **out.params)
        data = {"type": out.key, **({"order_id": out.order_id} if out.order_id else {}), **out.data}
        inbox = await self._claim(event_id, person, r, "in_app", data)
        if inbox is None:
            logger.info("message_already_sent", event_id=event_id, user_id=out.user_id, message=out.key)
            return {}
        await self._done(inbox, True)
        results: dict[str, str] = {"in_app": "sent"}
        channels = POLICY[out.key]
        pushed = False
        if "push" in channels and person.devices:
            nid = await self._claim(event_id, person, r, "push", data)
            if nid:
                res = await self.push.send(person.devices, PushMessage(r.title, r.body, data))
                await self.d.forget_devices(res.invalid)
                await self._done(nid, res.sent > 0)
                pushed = res.sent > 0
                results["push"] = "sent" if pushed else "failed"
        # SMS when it matters and push reached no device (none registered, or all failed).
        wants_sms = "sms" in channels or ("sms_fallback" in channels and not pushed)
        if wants_sms and person.phone:
            nid = await self._claim(event_id, person, r, "sms", data)
            if nid:
                ok = await get_sms_provider(person.country).send(person.phone, r.sms, person.country,
                                                                 r.dlt_template, r.params)
                await self._done(nid, ok)
                results["sms"] = "sent" if ok else "failed"
        if "email" in channels and person.email:
            nid = await self._claim(event_id, person, r, "email", data)
            if nid:
                code = out.params.get("code")  # receipts carry the order code even when the message doesn't
                subject = f"{r.title} · {code}" if code and code not in r.title else r.title
                ok = await self.email.send(person.email, subject, m.email_html(r, total=out.total, code=code),
                                           text=f"{r.title}\n\n{r.body}")
                await self._done(nid, ok)
                results["email"] = "sent" if ok else "failed"
        logger.info("message_sent", event_id=event_id, user_id=out.user_id, message=out.key, language=r.language, **results)
        return results


async def dispatch_event(event: dict[str, Any], db: AsyncSession, sender: Sender | None = None) -> list[dict[str, str]]:
    """Main entry point: one parsed domain event → its messages."""
    event_type = event.get("event_type", "")
    if event_type == notify.EVENT_TYPE:  # SMS/email requested by core_api (e.g. OTP)
        ok = await notify.deliver(event.get("payload", {}))
        logger.info("notify_delivered", channel=event.get("payload", {}).get("channel"), ok=ok)
        return []
    sender = sender or Sender(db)
    outgoing = await plan(event, sender.d)
    if not outgoing:
        logger.debug("no_message_for_event", event_type=event_type)
        return []
    event_id = str(event.get("event_id") or uuid.uuid4())
    return [await sender.deliver(event_id, o) for o in outgoing]
