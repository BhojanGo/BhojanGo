"""Order flow (P11): no order without payment, timeouts, outbox events.

    quote -> POST /orders (pending_payment) -> payment webhook -> placed
          -> restaurant accepts -> preparing -> (almost_ready) -> ready
          -> rider picks up -> delivered

Unpaid orders cancel after the unpaid_auto_cancel rule; placed orders the
restaurant doesn't accept within accept_timeout cancel and are refunded. Every
change writes an outbox event in the same transaction (shared/outbox.py).
"""
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.models.order import Order
from core_api.modules.orders.repository.order import OrderRepository
from core_api.modules.orders.schemas.order import OrderCancelRequest, OrderCreateRequest, OrderStatusUpdateRequest
from core_api.modules.orders.service import state_machine as sm
from shared import authz, outbox
from shared.auth import CurrentUser
from shared.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

SOURCE = "order-svc"
_CENTS = Decimal("0.01")
DEFAULT_UNPAID_MINUTES = 10
DEFAULT_ACCEPT_SECONDS = 180
DEFAULT_CANCEL_WINDOW_MINUTES = 2
PAYMENT_RETRY_MINUTES = 5  # after a failed payment the price stays held at least this long


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _err(code: int, key: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": key, "message": message})


def _event_payload(order: Order, **extra: object) -> dict:
    return {
        "order_id": str(order.id), "customer_id": str(order.customer_id), "restaurant_id": str(order.restaurant_id),
        "restaurant_name": order.restaurant_name, "status": order.status, "total": str(order.total),
        "currency": order.currency, "market_city": order.market_city,
        "driver_id": str(order.driver_id) if order.driver_id else None,
        # dispatch and tracking (P14)
        "pickup": [order.pickup_lat, order.pickup_lng] if order.pickup_lat is not None else None,
        "dropoff": [order.delivery_lat, order.delivery_lng] if order.delivery_lat is not None else None,
        # messages (P15)
        "estimated_delivery_time": order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
        "items_count": sum(int(i.get("quantity", 1)) for i in (order.items or [])),
        **extra,
    }


HANDOVER_MINUTES = 5  # parking, stairs, handing over


def delivery_eta(prep_minutes: int, pickup: tuple | None, dropoff: tuple | None, start: datetime) -> datetime:
    """When the food should arrive if the kitchen starts at ``start``: prep time,
    then the ride from the restaurant to the customer (routing provider), then handover."""
    from shared.providers.routing import get_routing_provider

    if pickup and dropoff and None not in (*pickup, *dropoff):
        ride = get_routing_provider().leg(pickup, dropoff).minutes  # type: ignore[arg-type]
    else:
        ride = float(settings.orders.BASE_DELIVERY_MINUTES)
    return start + timedelta(minutes=prep_minutes + ride + HANDOVER_MINUTES)


async def business_rules(db: AsyncSession, order: Order | None = None, context: dict | None = None) -> dict:
    """The order's business rules (timeouts, cancel window) from the rule engine."""
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    c = context or {}
    city = c.get("city") or (order.market_city if order else None)
    ctx = Context(country=c.get("country") or (city[:2] if city else None), region=c.get("region") or (city[:5] if city else None),
                  city=city, zone_id=c.get("zone_id") or (str(order.zone_id) if order and order.zone_id else None))
    rules = await RuleService(db).resolve(ctx)

    def get(template: str, field: str, default: int) -> int:
        r = rules.get(f"business:{template}")
        return int(r.params[field]) if r else default

    return {
        "unpaid_minutes": get("unpaid_auto_cancel", "minutes", DEFAULT_UNPAID_MINUTES),
        "accept_seconds": get("accept_timeout", "seconds", DEFAULT_ACCEPT_SECONDS),
        "cancel_window_minutes": get("cancel_window", "minutes", DEFAULT_CANCEL_WINDOW_MINUTES),
    }


class OrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = OrderRepository(db)

    # ── create: from a quote, waiting for payment ────────────────────────────
    async def create_order(self, data: OrderCreateRequest, customer_id: uuid.UUID, currency: str | None = None) -> Order:
        """Place an order at exactly the quoted price; it waits for payment."""
        from core_api.modules.pricing.service.quotes import QuoteError, QuoteService

        items = [
            {"menu_item_id": str(i.menu_item_id), "quantity": i.quantity,
             "options": i.picks()}
            for i in data.items
        ]
        quotes = QuoteService(self.db)
        try:
            q = await quotes.redeem(data.quote_token, customer_id, data.restaurant_id, items)
        except QuoteError as e:
            raise _err(status.HTTP_409_CONFLICT, "QUOTE_INVALID", str(e))

        def line_sum(*codes: str) -> Decimal:
            return _money(sum((Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] in codes), Decimal(0)))

        now = datetime.now(UTC)
        ctx = q["context"]
        rules = await business_rules(self.db, context=ctx)
        from core_api.modules.catalog.models.restaurant import Restaurant

        rest = await self.db.get(Restaurant, data.restaurant_id)
        drop = ctx.get("deliver_to") or {}
        from core_api.modules.catalog.service.menu import busy_minutes

        prep = (rest.avg_prep_minutes + busy_minutes(rest, now)) if rest else 20
        pickup = (rest.lat, rest.lng) if rest else None
        order = await self.repo.create(
            pickup_lat=rest.lat if rest else None,
            pickup_lng=rest.lng if rest else None,
            delivery_lat=drop.get("lat"),
            delivery_lng=drop.get("lng"),
            customer_id=customer_id,
            restaurant_id=data.restaurant_id,
            restaurant_name=q["restaurant_name"],
            items=[{**i, "unit_price": float(i["unit_price"]), "total": float(Decimal(i["unit_price"]) * i["quantity"])}
                   for i in q["items"]],
            status="pending_payment",
            market_city=ctx.get("city"),
            zone_id=uuid.UUID(ctx["zone_id"]) if ctx.get("zone_id") else None,
            payment_due_at=now + timedelta(minutes=rules["unpaid_minutes"]),
            subtotal=_money(q["food_subtotal"]),
            delivery_fee=line_sum("delivery_fee", "service_fee", "small_order_fee", "packaging", "surge", "late_night_fee"),
            taxes=line_sum("tax"),
            tip=line_sum("tip"),
            discount=-line_sum("promotion"),
            total=_money(q["total"]),
            currency=q["currency"],
            platform_fee=_money(q["split"]["platform"]),
            restaurant_payout=_money(q["split"]["restaurant"]),
            estimated_prep_minutes=prep,
            delivery_distance_km=_money(ctx["distance"]),
            is_long_distance=False,
            status_history=[{"status": "pending_payment", "at": now.isoformat()}],
            delivery_address=data.delivery_address.model_dump(),
            payment_method=data.payment_method,
            special_instructions=data.special_instructions,
            promo_code=data.promo_code,
            delivery_pin=f"{secrets.randbelow(10000):04d}",
            loyalty_points_used=0,
            estimated_delivery_time=delivery_eta(prep, pickup, (drop.get("lat"), drop.get("lng")), now),
        )
        try:
            await quotes.attach(q, order.id)
        except QuoteError as e:
            raise _err(status.HTTP_409_CONFLICT, "QUOTE_INVALID", str(e))
        await outbox.add(self.db, "order.created", "order", order.id,
                         _event_payload(order, payment_due_at=order.payment_due_at.isoformat()), SOURCE)  # type: ignore[union-attr]
        logger.info("order_created", order_id=str(order.id), customer_id=str(customer_id), quote_id=q["quote_id"])
        return order

    # ── payment ──────────────────────────────────────────────────────────────
    async def on_payment_succeeded(self, order_id: uuid.UUID) -> None:
        """Called by payments when an order's payment is captured (same transaction)."""
        order = await self._locked(order_id)
        if order is None:
            logger.warning("payment_for_unknown_order", order_id=str(order_id))
            return
        if order.status == "pending_payment":
            now = datetime.now(UTC)
            rules = await business_rules(self.db, order)
            await self._move(order, "placed", "system", extra={
                "placed_at": now, "accept_due_at": now + timedelta(seconds=rules["accept_seconds"])})
        elif order.status == "cancelled":
            # Paid after it was cancelled (e.g. unpaid timeout): give the money back.
            from core_api.modules.payments.service.order_payments import refund_in_full

            await refund_in_full(self.db, order.id, "paid_after_cancel")
            await outbox.add(self.db, "order.payment_after_cancel", "order", order.id, _event_payload(order), SOURCE)
        # placed or later: a duplicate notice; nothing to do

    async def on_payment_failed(self, order_id: uuid.UUID) -> None:
        """"Payment didn't go through": the order keeps its quoted price, and the
        customer gets at least PAYMENT_RETRY_MINUTES to try another way."""
        order = await self._locked(order_id)
        if order is None or order.status != "pending_payment":
            return
        floor = datetime.now(UTC) + timedelta(minutes=PAYMENT_RETRY_MINUTES)
        if order.payment_due_at is None or order.payment_due_at < floor:
            order.payment_due_at = floor
            await self.db.flush()

    # ── transitions ──────────────────────────────────────────────────────────
    async def actor_for(self, user: CurrentUser, order: Order, new_status: str) -> str | None:
        """Which actor the user is for this order, or None."""
        if order.market_city and authz.can([authz.Assignment.parse(a) for a in user.admin], "orders.edit", order.market_city):
            return "admin"
        if user.id == order.customer_id:
            return "customer"
        if user.role == "restaurant_owner":
            from core_api.modules.catalog.models.restaurant import Restaurant

            r = await self.db.get(Restaurant, order.restaurant_id)
            if r is not None and r.owner_id == user.id:
                return "restaurant"
        if user.role == "driver" and order.driver_id == user.id:  # assigned by dispatch (P14)
            return "rider"
        return None

    async def update_status(self, order_id: uuid.UUID, data: OrderStatusUpdateRequest, user: CurrentUser) -> Order:
        new = sm.LEGACY_NAMES.get(data.status, data.status)
        if new == "cancelled":
            return await self.cancel_order(order_id, OrderCancelRequest(reason="other", note=data.note), user)
        order = await self._locked(order_id)
        if order is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        actor = await self.actor_for(user, order, new)
        if actor is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        if not sm.can_transition(order.status, new):
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"Can't go from {order.status} to {new}")
        if not sm.actor_allowed(order.status, new, actor):
            raise _err(status.HTTP_403_FORBIDDEN, "FORBIDDEN", f"You can't move this order to {new}")
        now = datetime.now(UTC)
        extra: dict = {}
        if new == "accepted":
            prep = data.prep_minutes or order.estimated_prep_minutes  # the kitchen picks "ready in" (P19)
            extra = {"restaurant_accepted_at": now, "accept_due_at": None, "estimated_prep_minutes": prep,
                     "estimated_delivery_time": delivery_eta(
                         prep, (order.pickup_lat, order.pickup_lng),
                         (order.delivery_lat, order.delivery_lng), now)}
        elif new == "ready":
            extra = {"actual_ready_at": now}
        elif new == "picked_up":
            extra = {"picked_up_at": now}
        elif new == "delivered":
            extra = {"actual_delivery_time": now}
            proof = await self._delivery_proof(order, data, actor, user)
            if proof:
                extra["delivery_proof"] = proof
        return await self._move(order, new, actor, note=data.note, extra=extra)

    @staticmethod
    async def _delivery_proof(order: Order, data: OrderStatusUpdateRequest, actor: str, user: CurrentUser) -> dict | None:
        """A rider proves the drop-off with the customer's PIN or a photo of the
        bags at the door (P18). Admins (support) may mark delivered without one."""
        p = data.proof
        if p is None:
            if actor == "rider":
                raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "PROOF_REQUIRED",
                           "Enter the customer's PIN or take a photo at the door")
            return None
        at = datetime.now(UTC).isoformat()
        if p.method == "pin":
            if not p.pin or (order.delivery_pin and not secrets.compare_digest(p.pin, order.delivery_pin)):
                raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "PIN_WRONG", "That PIN doesn't match. Ask the customer again")
            return {"method": "pin", "at": at}
        # Only a photo this rider uploaded for proof (see POST /uploads).
        from shared.providers.storage import get_storage

        if (not p.photo_key or not p.photo_key.startswith(f"delivery_proof/{user.user_id}/")
                or not await get_storage().exists(p.photo_key)):
            raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "PHOTO_REQUIRED", "Take a photo of the bags at the door")
        return {"method": "photo", "photo_key": p.photo_key, "at": at}

    async def cancel_order(self, order_id: uuid.UUID, data: OrderCancelRequest, user: CurrentUser) -> Order:
        order = await self._locked(order_id)
        if order is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        actor = await self.actor_for(user, order, "cancelled")
        if actor is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        if not sm.actor_allowed(order.status, "cancelled", actor):
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"This order can't be cancelled now ({order.status})")
        if actor == "customer" and order.status == "accepted":
            window = (await business_rules(self.db, order))["cancel_window_minutes"]
            if order.placed_at and datetime.now(UTC) > order.placed_at + timedelta(minutes=window):
                raise _err(status.HTTP_409_CONFLICT, "CANCEL_WINDOW_PASSED",
                           "The restaurant has started on your order; contact support to cancel")
        return await self._cancel(order, actor, data.reason, data.note)

    # ── dispatch (called by realtime over the internal API) ──────────────────
    async def assign_rider(self, order_id: uuid.UUID, rider_id: uuid.UUID) -> Order:
        """A rider accepted the offer. Idempotent for the same rider."""
        order = await self._locked(order_id)
        if order is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        if order.driver_id == rider_id:
            return order
        if order.driver_id is not None:
            raise _err(status.HTTP_409_CONFLICT, "ALREADY_ASSIGNED", "Another rider has this order")
        if order.status not in ("accepted", "preparing", "almost_ready", "ready"):
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"Can't assign a rider to a {order.status} order")
        order.driver_id, order.rider_assigned_at = rider_id, datetime.now(UTC)
        await self.db.flush()
        from core_api.modules.identity.service.profile import user_profile

        profile = await user_profile(self.db, rider_id) or {}
        await outbox.add(self.db, "driver.assigned", "order", order.id,
                         _event_payload(order, driver_name=profile.get("name", "your rider")), SOURCE)
        logger.info("rider_assigned", order_id=str(order.id), rider_id=str(rider_id))
        await self.db.refresh(order)
        return order

    # ── timeouts ─────────────────────────────────────────────────────────────
    async def sweep(self, now: datetime | None = None, limit: int = 100) -> dict[str, int]:
        """Cancel unpaid orders past payment_due_at and placed orders past
        accept_due_at (refunded). Safe with several core_api replicas."""
        now = now or datetime.now(UTC)
        counts = {"payment_timeout": 0, "restaurant_no_response": 0}
        for state, due, reason in (("pending_payment", Order.payment_due_at, "payment_timeout"),
                                   ("placed", Order.accept_due_at, "restaurant_no_response")):
            rows = (await self.db.execute(
                select(Order).where(Order.status == state, due.is_not(None), due < now)
                .order_by(due).limit(limit).with_for_update(skip_locked=True)
            )).scalars().all()
            for order in rows:
                try:
                    async with self.db.begin_nested():  # one bad order must not stop the rest
                        await self._cancel(order, "system", reason, None)
                    counts[reason] += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("order_timeout_failed", order_id=str(order.id), reason=reason, error=str(e))
        if any(counts.values()):
            logger.info("order_timeouts_swept", **counts)
        return counts

    # ── internals ────────────────────────────────────────────────────────────
    async def _locked(self, order_id: uuid.UUID) -> Order | None:
        return (await self.db.execute(select(Order).where(Order.id == order_id).with_for_update())).scalar_one_or_none()

    async def _move(self, order: Order, new: str, actor: str, note: str | None = None, extra: dict | None = None) -> Order:
        previous = order.status
        now = datetime.now(UTC)
        order.status = new
        order.status_history = [*(order.status_history or []), {"status": new, "at": now.isoformat(), "by": actor}]
        for k, v in (extra or {}).items():
            setattr(order, k, v)
        await self.db.flush()
        await outbox.add(self.db, "order.placed" if new == "placed" else "order.status_changed", "order", order.id,
                         _event_payload(order, previous_status=previous, new_status=new, by=actor, note=note), SOURCE)
        logger.info("order_status_changed", order_id=str(order.id), previous=previous, new=new, by=actor)
        await self.db.refresh(order)  # server-set columns (updated_at) for the response
        return order

    async def _cancel(self, order: Order, actor: str, reason: str, note: str | None) -> Order:
        was_paid = order.status in sm.PAID_STATES
        now = datetime.now(UTC)
        previous = order.status
        order.status, order.cancelled_at, order.cancelled_by = "cancelled", now, actor
        order.cancellation_reason, order.cancellation_note = reason, note
        order.payment_due_at = order.accept_due_at = None
        order.status_history = [*(order.status_history or []), {"status": "cancelled", "at": now.isoformat(), "by": actor}]
        await self.db.flush()
        refund = None
        if was_paid:
            from core_api.modules.payments.service.order_payments import refund_in_full

            try:
                async with self.db.begin_nested():
                    refund = await refund_in_full(self.db, order.id, reason)
            except Exception as e:  # noqa: BLE001 - the order is still cancelled; finance retries the refund
                logger.error("order_refund_failed", order_id=str(order.id), error=str(e))
                await outbox.add(self.db, "payment.refund_failed", "order", order.id,
                                 _event_payload(order, reason=reason, error=str(e)[:300]), SOURCE)
        await outbox.add(self.db, "order.cancelled", "order", order.id, _event_payload(
            order, previous_status=previous, reason=reason, by=actor,
            refund_amount=refund["amount"] if refund else 0), SOURCE)
        logger.info("order_cancelled", order_id=str(order.id), previous=previous, reason=reason, by=actor, refunded=bool(refund))
        await self.db.refresh(order)
        return order
