"""R39: chargebacks (Stripe ``charge.dispute.created`` / ``.updated`` / ``.closed``).

* Opened: the dispute is recorded against its order (admin Finance > Disputes; the order shows it),
  ops are alerted (Operations page + the paging webhook), and the restaurant's share of the order
  (its payout less the card fee, at most the disputed amount) is held from its next payout run.
* Evidence: finance uploads files and a note in admin, then submits them to the provider.
* Closed, won (or an inquiry closed with no chargeback): the hold comes back on the next payout run.
* Closed, lost: the loss is recorded per the restaurant agreement. Default: the restaurant bears the food
  amount when the reason is about the food (Stripe ``product_unacceptable``); BhojanGo bears everything
  else (fraud, not received, duplicate, ...). A country may list other restaurant reasons in its Markets
  setting ``dispute_restaurant_reasons``. The restaurant's part comes off the next payout (net of what was
  held); BhojanGo's part is recorded as ``platform_loss``. The provider's dispute fee is BhojanGo's.
Amounts are minor units. Each event is applied once (processed_webhook_events), in any order.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.models.payment import PaymentDispute, PaymentIntent
from shared import outbox

logger = structlog.get_logger(__name__)

RESTAURANT_REASONS: tuple[str, ...] = ("product_unacceptable",)
CLOSED = {"won", "lost", "warning_closed", "charge_refunded"}
ALERT = "ChargebackOpened"


def fingerprint(d: PaymentDispute) -> str:
    return f"dispute:{d.provider_dispute_id}"[:64]


def _minor(v: Decimal | None) -> int:
    return int((Decimal(v or 0) * 100).to_integral_value())


def outcome_of(status: str) -> str | None:
    """won | lost for a closed dispute; None while open. An inquiry closed without a chargeback, or a
    charge refunded before it became one, costs nothing: shown as won."""
    if status == "lost":
        return "lost"
    if status in CLOSED:
        return "won"
    return None


def split_loss(reason: str, amount: int, food: int, restaurant_reasons: tuple[str, ...] = RESTAURANT_REASONS
               ) -> tuple[str, int, int]:
    """(who bears it, the restaurant's part, BhojanGo's part) of a lost dispute."""
    if reason in restaurant_reasons:
        theirs = max(0, min(food, amount))
        return "restaurant", theirs, amount - theirs
    return "platform", 0, amount


async def _restaurant_reasons(db: AsyncSession, country: str | None) -> tuple[str, ...]:
    from core_api.modules.markets.models import Country

    if not country:
        return RESTAURANT_REASONS
    c = (await db.execute(select(Country).where(Country.code == country))).scalars().first()
    got = ((c.settings or {}) if c else {}).get("dispute_restaurant_reasons")
    return tuple(str(r) for r in got) if isinstance(got, list) else RESTAURANT_REASONS


def _when(v) -> datetime | None:  # type: ignore[no-untyped-def]
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromtimestamp(int(v), UTC)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(v))
        except ValueError:
            return None


async def apply_dispute_event(db: AsyncSession, provider: str, event: dict) -> dict:
    """Record or update a dispute from the provider's event (``event["dispute"]``)."""
    from core_api.modules.orders.models.order import Order
    from core_api.modules.support.service.alerts import raise_alert, resolve_alert
    from shared.money import format_money

    d = event.get("dispute") or {}
    if not d.get("id"):
        return {"received": True, "ignored": "no dispute"}
    row = (await db.execute(select(PaymentDispute).where(PaymentDispute.provider_dispute_id == d["id"])
                            .with_for_update())).scalars().first()
    status = str(d.get("status") or "needs_response")[:30]
    now = datetime.now(UTC)
    if row is None:
        intent = None
        if d.get("payment_intent"):
            intent = (await db.execute(select(PaymentIntent).where(
                PaymentIntent.provider_payment_id == d["payment_intent"]))).scalars().first()
        order = await db.get(Order, intent.order_id) if intent else None
        amount = int(d.get("amount") or 0)
        share = max(0, _minor(order.restaurant_payout) - _minor(order.card_fee)) if order else 0
        city = order.market_city if order else None
        row = PaymentDispute(
            id=uuid.uuid4(), provider=provider, provider_dispute_id=d["id"], provider_payment_id=d.get("payment_intent"),
            order_id=order.id if order else None, restaurant_id=order.restaurant_id if order else None,
            country=(city or "")[:2] or None, market_city=city,
            currency=str(d.get("currency") or (order.currency if order else "USD")).upper(), amount=amount,
            reason=str(d.get("reason") or "general")[:40], status=status, held=min(share, amount), evidence=[],
            restaurant_loss=0, platform_loss=0,
            evidence_due_by=_when(d.get("due_by")), opened_at=_when(d.get("created")) or now)
        db.add(row)
        await db.flush()
        money = lambda minor: format_money(Decimal(minor) / 100, row.currency)  # noqa: E731
        code = str(row.order_id)[:8].upper() if row.order_id else "unknown"
        due = f" before {row.evidence_due_by:%d %b %Y}" if row.evidence_due_by else ""
        await raise_alert(
            db, fingerprint(row), ALERT,
            f"Chargeback opened: {money(amount)}{' in ' + city if city else ''} ({row.reason.replace('_', ' ')})",
            f"Order {code}: the restaurant's share ({money(row.held)}) is held from its next payout. "
            f"Add evidence in admin Finance > Disputes{due}.",
            severity="warning", city=city, page=True, now=now)
        await outbox.add(db, "payment.dispute_opened", "order", row.order_id or row.id, {
            "dispute_id": str(row.id), "order_id": str(row.order_id) if row.order_id else None, "amount": amount,
            "currency": row.currency, "reason": row.reason, "held": row.held}, "payment-svc")
        logger.warning("dispute_opened", dispute=d["id"], order_id=str(row.order_id), amount=amount, reason=row.reason)
    else:
        row.status = status
        if d.get("reason"):
            row.reason = str(d["reason"])[:40]
        if d.get("amount"):
            row.amount = int(d["amount"])
        if d.get("due_by"):
            row.evidence_due_by = _when(d["due_by"])
    outcome = outcome_of(status)
    if outcome and row.outcome is None:
        await _close(db, row, outcome, now)
        await resolve_alert(db, fingerprint(row), now)
    await db.flush()
    return {"received": True, "dispute": str(row.id), "status": row.status, "outcome": row.outcome}


async def _close(db: AsyncSession, row: PaymentDispute, outcome: str, now: datetime) -> None:
    from core_api.modules.orders.models.order import Order

    row.outcome, row.closed_at = outcome, now
    if outcome == "lost":
        order = await db.get(Order, row.order_id) if row.order_id else None
        food = _minor(order.subtotal) if order else 0
        row.loss_bearer, row.restaurant_loss, row.platform_loss = split_loss(
            row.reason, row.amount, food, await _restaurant_reasons(db, row.country))
    await outbox.add(db, "payment.dispute_closed", "order", row.order_id or row.id, {
        "dispute_id": str(row.id), "order_id": str(row.order_id) if row.order_id else None, "outcome": outcome,
        "restaurant_loss": row.restaurant_loss, "platform_loss": row.platform_loss, "currency": row.currency}, "payment-svc")
    logger.info("dispute_closed", dispute=row.provider_dispute_id, outcome=outcome, bearer=row.loss_bearer,
                restaurant_loss=row.restaurant_loss, platform_loss=row.platform_loss)


# ── the payout run ───────────────────────────────────────────────────────────

@dataclass
class Adjustment:
    dispute: PaymentDispute
    amount: int  # minor units added to the restaurant's statement (< 0 held or charged, > 0 released)
    kind: str  # dispute_hold | dispute_released | dispute_loss | dispute_settled


def adjustment(d: PaymentDispute) -> Adjustment | None:
    """What the next payout run does with this dispute, if anything."""
    if d.outcome is None:
        return Adjustment(d, -d.held, "dispute_hold") if d.hold_statement_id is None and d.held > 0 else None
    if d.settle_statement_id is not None:
        return None
    held = d.held if d.hold_statement_id is not None else 0
    delta = held - d.restaurant_loss
    if delta == 0 and held == 0:
        return None  # never held, nothing to charge
    kind = "dispute_released" if delta > 0 else ("dispute_loss" if delta < 0 else "dispute_settled")
    return Adjustment(d, delta, kind)


async def payout_adjustments(db: AsyncSession, country: str, lock: bool = False) -> dict[str, list[Adjustment]]:
    """Per restaurant: the holds, releases and losses the next payout run applies."""
    q = select(PaymentDispute).where(
        PaymentDispute.country == country, PaymentDispute.restaurant_id.is_not(None),
        or_(PaymentDispute.hold_statement_id.is_(None), PaymentDispute.settle_statement_id.is_(None)))
    if lock:
        q = q.with_for_update()
    found: dict[str, list[Adjustment]] = defaultdict(list)
    for d in (await db.execute(q)).scalars():
        a = adjustment(d)
        if a is not None:
            found[str(d.restaurant_id)].append(a)
    return dict(found)


def mark_applied(adjustments: list[Adjustment], statement_id: uuid.UUID) -> None:
    for a in adjustments:
        if a.kind == "dispute_hold":
            a.dispute.hold_statement_id = statement_id
        else:
            a.dispute.settle_statement_id = statement_id
            if a.dispute.hold_statement_id is None:
                a.dispute.hold_statement_id = statement_id


def summary_lines(adjustments: list[Adjustment]) -> list[dict]:
    return [{"dispute_id": str(a.dispute.id), "order_id": str(a.dispute.order_id) if a.dispute.order_id else None,
             "kind": a.kind, "amount": a.amount, "reason": a.dispute.reason} for a in adjustments]


def dispute_out(d: PaymentDispute, restaurant: str | None = None) -> dict:
    a = adjustment(d)
    return {"id": str(d.id), "provider": d.provider, "provider_dispute_id": d.provider_dispute_id,
            "order_id": str(d.order_id) if d.order_id else None,
            "order_code": str(d.order_id)[:8].upper() if d.order_id else None,
            "restaurant_id": str(d.restaurant_id) if d.restaurant_id else None, "restaurant": restaurant,
            "country": d.country, "city": d.market_city, "currency": d.currency, "amount": d.amount, "reason": d.reason,
            "status": d.status, "outcome": d.outcome, "held": d.held,
            "hold_applied": d.hold_statement_id is not None, "settled": d.settle_statement_id is not None,
            "next_payout": a.amount if a else 0, "loss_bearer": d.loss_bearer, "restaurant_loss": d.restaurant_loss,
            "platform_loss": d.platform_loss,
            "evidence": [{k: e.get(k) for k in ("n", "name", "content_type", "size", "note", "uploaded_at")}
                         for e in d.evidence or []],
            "evidence_submitted_at": d.evidence_submitted_at.isoformat() if d.evidence_submitted_at else None,
            "evidence_due_by": d.evidence_due_by.isoformat() if d.evidence_due_by else None,
            "opened_at": d.opened_at.isoformat() if d.opened_at else None,
            "closed_at": d.closed_at.isoformat() if d.closed_at else None}
