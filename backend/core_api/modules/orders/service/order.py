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
from core_api.modules.orders.service.pin import delivery_pin
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


PICKUP_CODE_TRIES = 5  # R32: then the order is locked until support helps


def _event_payload(order: Order, **extra: object) -> dict:
    return {
        "order_id": str(order.id), "customer_id": str(order.customer_id), "restaurant_id": str(order.restaurant_id),
        "restaurant_name": order.restaurant_name, "status": order.status, "total": str(order.total),
        "currency": order.currency, "market_city": order.market_city,
        "fulfillment": order.fulfillment or "delivery",  # R32: realtime never dispatches a pickup order
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


def order_eta(fulfillment: str | None, prep_minutes: int, pickup: tuple | None, dropoff: tuple | None,
              start: datetime) -> datetime:
    """R34: a pickup order's estimate is when it'll be READY (prep time only: no ride, no handover);
    a delivery order's is when it arrives at the door."""
    if fulfillment == "pickup":
        return start + timedelta(minutes=prep_minutes)
    return delivery_eta(prep_minutes, pickup, dropoff, start)


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


CUSTOMER_CANCEL_STATES = ("pending_payment", "placed", "accepted")


def customer_cancel_window(status: str, placed_at: datetime | None, window_minutes: int,
                           now: datetime) -> tuple[bool, datetime | None]:
    """May the customer cancel now, and until when (R8; the one rule, used by the cancel
    itself and by GET /orders/{id}). Before the kitchen accepts: yes (no time limit of its
    own: the kitchen's accept timeout cancels it anyway). Accepted: for window_minutes
    after the order was placed, while the kitchen hasn't started cooking. Later: no."""
    if status not in CUSTOMER_CANCEL_STATES:
        return False, None
    if status != "accepted":
        return True, None
    if placed_at is None:
        return True, None
    until = placed_at + timedelta(minutes=window_minutes)
    return now <= until, until


async def customer_cancel(db: AsyncSession, order: Order, now: datetime | None = None) -> dict | None:
    """What the customer's "Cancel order" needs (OrderResponse.customer_cancel), or None."""
    if order.status not in CUSTOMER_CANCEL_STATES:
        return None
    window = (await business_rules(db, order))["cancel_window_minutes"] if order.status == "accepted" else 0
    allowed, until = customer_cancel_window(order.status, order.placed_at, window, now or datetime.now(UTC))
    if not allowed:
        return None
    paid = order.status in sm.PAID_STATES
    return {"until": until, "refund": float(order.total) if paid else 0.0, "refund_to": order.payment_method}


async def refunded_total(db: AsyncSession, order_id: uuid.UUID) -> float | None:
    """Everything refunded on an order (major units), or None when nothing was."""
    from sqlalchemy import func

    from core_api.modules.payments.models.payment import Refund

    minor = (await db.execute(select(func.sum(Refund.amount)).where(Refund.order_id == order_id))).scalar()
    return float(minor) / 100 if minor else None


async def refunded_totals(db: AsyncSession, order_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """R28: refunded_total for many orders in one query (the orders list); orders with none are left out."""
    if not order_ids:
        return {}
    from sqlalchemy import func

    from core_api.modules.payments.models.payment import Refund

    rows = await db.execute(select(Refund.order_id, func.sum(Refund.amount))
                            .where(Refund.order_id.in_(order_ids)).group_by(Refund.order_id))
    return {oid: float(minor) / 100 for oid, minor in rows.all() if minor}


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
        except QuoteError as e:  # R36: BELOW_MINIMUM (the restaurant's own minimum) keeps its code
            raise _err(status.HTTP_409_CONFLICT, "BELOW_MINIMUM" if e.code == "BELOW_MINIMUM" else "QUOTE_INVALID", str(e))

        def line_sum(*codes: str) -> Decimal:
            return _money(sum((Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] in codes), Decimal(0)))

        now = datetime.now(UTC)
        ctx = q["context"]
        rules = await business_rules(self.db, context=ctx)
        from core_api.modules.catalog.models.restaurant import Restaurant

        rest = await self.db.get(Restaurant, data.restaurant_id)
        # R17: a quote is good for 10 minutes; an incident pause since then still stops the order.
        from core_api.modules.incidents.service import pause_for, pause_message

        paused = await pause_for(self.db, ctx.get("city"))
        if paused is not None:
            raise _err(status.HTTP_409_CONFLICT, "ORDERING_PAUSED", pause_message(paused))
        if rest is not None and rest.closed_for_now:
            raise _err(status.HTTP_409_CONFLICT, "KITCHEN_PAUSED", f"{rest.name} is closed for now")
        if rest is not None:
            # R27: a quote is good for 10 minutes; a kitchen that closed since (its hours, the city's
            # delivery hours, paused) takes no order.
            from core_api.modules.catalog.service.menu import availability

            avail = await availability(self.db, rest.id, now)
            # Closed by its hours first; a kitchen open by its hours but with no live tablet: KITCHEN_OFFLINE below.
            if not avail.open_now and avail.reason_code != "not_taking_orders":
                raise _err(status.HTTP_409_CONFLICT, "KITCHEN_CLOSED", f"{rest.name}: {avail.reason}")
        # R27: no order for a kitchen whose tablet isn't connected (nobody would see it).
        from core_api.modules.catalog.service.menu import tablet_offline

        offline = await tablet_offline(self.db, data.restaurant_id)
        if offline:
            raise _err(status.HTTP_409_CONFLICT, "KITCHEN_OFFLINE", offline)
        drop = ctx.get("deliver_to") or {}
        fulfillment = ctx.get("fulfillment", "delivery")  # R32: the quote decides
        if fulfillment == "delivery" and data.delivery_address is None:
            raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "ADDRESS_REQUIRED", "Choose where to deliver")
        from core_api.modules.catalog.service.menu import busy_minutes

        prep = (rest.avg_prep_minutes + busy_minutes(rest, now)) if rest else 20
        pickup = (rest.lat, rest.lng) if rest else None
        await self._add_payment_fees(q, data.payment_method)  # R29: before the order, so a cash order's payout has no card fee
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
            delivery_fee=line_sum("delivery_fee", "platform_fee", "service_fee", "small_order_fee", "packaging", "surge", "late_night_fee"),
            taxes=line_sum("tax"),
            tip=line_sum("tip"),
            discount=-line_sum("promotion"),
            total=_money(q["total"]),
            currency=q["currency"],
            platform_fee=_money(q["split"]["platform"]),
            restaurant_payout=_money(q["split"]["restaurant"]),
            card_fee=_money(q["split"].get("card_fee", "0")),
            estimated_prep_minutes=prep,
            delivery_distance_km=_money(ctx["distance"]),
            is_long_distance=False,
            status_history=[{"status": "pending_payment", "at": now.isoformat()}],
            delivery_address=(data.delivery_address.model_dump() if fulfillment == "delivery"
                              else {**(ctx.get("pickup_address") or {}), "pickup": True}),
            fulfillment=fulfillment,
            payment_method=data.payment_method,
            special_instructions=data.special_instructions,
            promo_code=data.promo_code,
            delivery_pin=delivery_pin(),
            loyalty_points_used=0,
            estimated_delivery_time=order_eta(fulfillment, prep, pickup, (drop.get("lat"), drop.get("lng")), now),
        )
        try:
            await quotes.attach(q, order.id)
        except QuoteError as e:  # R37: OFFER_ENDED: the month's offer budget ran out since the quote
            raise _err(status.HTTP_409_CONFLICT, "OFFER_ENDED" if e.code == "OFFER_ENDED" else "QUOTE_INVALID", str(e))
        await outbox.add(self.db, "order.created", "order", order.id,
                         _event_payload(order, payment_due_at=order.payment_due_at.isoformat()), SOURCE)  # type: ignore[union-attr]
        logger.info("order_created", order_id=str(order.id), customer_id=str(customer_id), quote_id=q["quote_id"])
        if ctx.get("review"):
            await self._place_review_order(order)
        return order

    async def _place_review_order(self, order: Order) -> None:
        """R20: an app store review account's order in its review-only city was quoted at
        zero (pricing engine ``review``). Checked again here, then placed at once with no
        payment provider (payments.place_review_order). Anything else waits for payment."""
        from core_api.modules.markets.service import review
        from core_api.modules.payments.service.order_payments import place_review_order

        settings_ = await review.city_settings(self.db, order.market_city)
        if order.total != 0 or not review.is_review_account(settings_, order.customer_id):
            logger.error("review_order_refused", order_id=str(order.id), total=str(order.total), city=order.market_city)
            return  # it waits for payment like any order
        await place_review_order(self.db, order.id, order.customer_id, order.currency)

    async def _add_payment_fees(self, q: dict, method: str) -> None:
        """Payment fees (item 1) go into the order's split once the method is known:
        "Payment fees", and "platform keeps" = platform after them. Refunds come off
        later, in finance's contribution report."""
        from core_api.modules.pricing.service.engine import payment_fee
        from core_api.modules.rules.service.resolver import Context
        from core_api.modules.rules.service.rules import RuleService

        ctx = q["context"]
        rule = (await RuleService(self.db).resolve(Context(country=ctx.get("country"), region=ctx.get("region"),
                                                           city=ctx.get("city")))).get("business:payment_fees")
        tax_calculated = any((ln.get("detail") or {}).get("provider") for ln in q["lines"] if ln.get("code") == "tax")
        if any(r.get("slot") == "fee:card_fee_estimate" for r in q["rules_used"]):
            # R29 fee model v2: the card fee comes off the restaurant's payout (engine split); the platform
            # pays only the tax service. A cash order has no card fee: the restaurant gets it back.
            # R30: re-priced at the chosen method's rate (UPI, wallet, net banking...); cash has none.
            split = dict(q["split"])
            quoted = Decimal(split.get("card_fee", "0"))
            card = await self._method_fee(q, method)
            if card != quoted:
                split["restaurant"] = str(_money(Decimal(split["restaurant"]) + quoted - card))
                split["card_fee"] = str(card)
                split["detail"] = {**split.get("detail", {}), "card_fee": str(card)}
            tax_service = Decimal(0)
            if rule and tax_calculated and method != "cash_on_delivery":
                tax_service = _money(Decimal(q["total"]) * Decimal(str(rule.params.get("tax_service_percent", 0))) / 100)
            fee = _money(card + tax_service)
            q["split"] = {**split, "payment_fees": str(fee), "platform_keeps": str(_money(Decimal(split["platform"]) - tax_service)),
                          "detail": {**split.get("detail", {}), "payment_fees": {"method": method, "processing": str(card),
                                                                               "tax_service": str(tax_service),
                                                                               "processing_paid_by": "restaurant",
                                                                               "estimated": True}}}
        else:
            fee, detail = payment_fee(Decimal(q["total"]), method, rule.params if rule else None, tax_calculated)
            q["split"] = {**q["split"], "payment_fees": str(fee),
                          "platform_keeps": str(Decimal(q["split"]["platform"]) - fee),
                          "detail": {**q["split"].get("detail", {}), "payment_fees": detail}}
        if rule:
            q["rules_used"] = [*q["rules_used"], {"rule_id": str(rule.id), "rule_key": str(rule.rule_key), "version": rule.version,
                                                 "slot": rule.slot, "scope_level": rule.scope_level, "scope_id": rule.scope_id}]

    async def _method_fee(self, q: dict, method: str) -> Decimal:
        """R30: the payment fee estimate for this method, from the estimate rule the quote used."""
        from core_api.modules.pricing.service.fees import card_fee_cents, from_cents, method_rate, to_cents
        from core_api.modules.rules.models import Rule

        ref = next(r for r in q["rules_used"] if r.get("slot") == "fee:card_fee_estimate")
        rule = await self.db.get(Rule, uuid.UUID(ref["rule_id"]))
        rate = method_rate(rule.params, method) if rule else None
        if not rate or Decimal(q["total"]) <= 0:
            return Decimal("0.00")
        tip = Decimal(str((q["split"].get("detail") or {}).get("tip") or 0))
        return from_cents(card_fee_cents(to_cents(q["total"]), to_cents(tip), rate["percent"], to_cents(rate.get("fixed", 0))))

    async def apply_reported_method(self, order_id: uuid.UUID, reported: str) -> None:
        """R31, local and QA: the gateway said how the customer actually paid inside its checkout (e.g. a
        Paytm wallet on Razorpay); the estimate is re-priced at that method's rate. Production uses the
        gateway's actual fee instead (apply_actual_card_fee)."""
        from core_api.modules.pricing.models import OrderPricingSnapshot
        from core_api.modules.pricing.service.fees import GATEWAY_METHOD, card_fee_cents, from_cents, method_rate, to_cents
        from core_api.modules.rules.models import Rule

        method = GATEWAY_METHOD.get((reported or "").lower())
        order = await self._locked(order_id)
        if method is None or order is None or order.payment_method in ("cash_on_delivery", "wallet"):
            return
        snap = (await self.db.execute(select(OrderPricingSnapshot).where(OrderPricingSnapshot.order_id == order.id))).scalar()
        ref = next((v for v in (snap.rule_versions if snap else []) if v.get("slot") == "fee:card_fee_estimate"), None)
        rule = await self.db.get(Rule, uuid.UUID(ref["rule_id"])) if ref else None
        rate = method_rate(rule.params, method) if rule else None
        if rate is None:
            return
        fee = from_cents(card_fee_cents(to_cents(order.total), to_cents(order.tip or 0), rate["percent"],
                                        to_cents(rate.get("fixed", 0))))
        if fee == order.card_fee:
            return
        before = order.card_fee or Decimal(0)
        order.restaurant_payout = _money(order.restaurant_payout + before - fee)
        order.card_fee = fee
        await self.db.flush()
        logger.info("card_fee_method", order_id=str(order_id), reported=reported, estimate=str(before), now=str(fee))

    async def apply_actual_card_fee(self, order_id: uuid.UUID, fee_minor: int) -> None:
        """R29, production only: the gateway's actual fee for the payment (R30: any method: card, UPI,
        wallet, net banking) replaces the estimate taken from the restaurant's payout at placement (only
        for orders priced with a payment fee estimate)."""
        from core_api.modules.pricing.models import OrderPricingSnapshot

        order = await self._locked(order_id)
        if order is None or order.payment_method == "cash_on_delivery":
            return
        settings_ = (await self.db.execute(select(OrderPricingSnapshot.fee_settings)
                                           .where(OrderPricingSnapshot.order_id == order.id))).scalar()
        if not settings_:  # priced before fee model v2: the platform pays the processing fee
            return
        actual = (Decimal(fee_minor) / 100).quantize(Decimal("0.01"))
        if actual == order.card_fee:
            return
        before = order.card_fee or Decimal(0)
        order.restaurant_payout = _money(order.restaurant_payout + before - actual)
        order.card_fee = actual
        await self.db.flush()
        logger.info("card_fee_actual", order_id=str(order_id), estimate=str(before), actual=str(actual))

    # ── payment ──────────────────────────────────────────────────────────────
    async def on_payment_succeeded(self, order_id: uuid.UUID) -> None:
        """Called by payments when an order's payment is captured (same transaction)."""
        order = await self._locked(order_id)
        if order is None:
            logger.warning("payment_for_unknown_order", order_id=str(order_id))
            return
        if order.status == "pending_payment":
            from core_api.modules.catalog.service.menu import tablet_offline

            if await tablet_offline(self.db, order.restaurant_id):
                # R27: paid while the kitchen's tablet went silent (payment was refused for such a
                # kitchen up to the moment it started): nobody would see it, so it is cancelled
                # and refunded at once rather than waiting out the accept timer.
                await self._cancel(order, "system", "restaurant_no_response", "The restaurant's tablet wasn't connected", paid=True)
                return
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
        if not sm.can_transition(order.status, new) or not sm.fits(order.fulfillment, order.status, new):
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"Can't go from {order.status} to {new}")
        if order.fulfillment == "pickup" and new == "delivered" and actor != "admin":
            raise _err(status.HTTP_409_CONFLICT, "PICKUP_CODE_REQUIRED", "Enter the customer's pickup code")
        if not sm.actor_allowed(order.status, new, actor):
            raise _err(status.HTTP_403_FORBIDDEN, "FORBIDDEN", f"You can't move this order to {new}")
        now = datetime.now(UTC)
        extra: dict = {}
        if new == "accepted":
            prep = data.prep_minutes or order.estimated_prep_minutes  # the kitchen picks "ready in" (P19)
            extra = {"restaurant_accepted_at": now, "accept_due_at": None, "estimated_prep_minutes": prep,
                     "estimated_delivery_time": order_eta(
                         order.fulfillment, prep, (order.pickup_lat, order.pickup_lng),
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

    async def collect_pickup(self, order_id: uuid.UUID, code: str, user: CurrentUser) -> Order:
        """R32: the restaurant enters the customer's pickup code: the order is collected. A wrong code is
        refused and counted (the count is kept even though the request fails); 5 wrong codes lock the order:
        the restaurant calls support, who can complete it (admins mark it delivered)."""
        order = await self._locked(order_id)
        if order is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        actor = await self.actor_for(user, order, "delivered")
        if actor not in ("restaurant", "admin"):
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        if order.fulfillment != "pickup" or order.status != "ready":
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", "This order isn't waiting for pickup")
        if order.pickup_locked_at is not None:
            raise _err(status.HTTP_423_LOCKED, "PICKUP_LOCKED",
                       "Too many wrong codes. Call BhojanGo support to hand this order over")
        if not order.delivery_pin or not secrets.compare_digest(code, order.delivery_pin):
            order.pickup_code_attempts = (order.pickup_code_attempts or 0) + 1
            left = PICKUP_CODE_TRIES - order.pickup_code_attempts
            if left <= 0:
                order.pickup_locked_at = datetime.now(UTC)
            await self.db.commit()  # the wrong try counts, though this request fails
            logger.warning("pickup_code_wrong", order_id=str(order.id), attempts=order.pickup_code_attempts)
            if left <= 0:
                raise _err(status.HTTP_423_LOCKED, "PICKUP_LOCKED",
                           "Too many wrong codes. Call BhojanGo support to hand this order over")
            raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "PICKUP_CODE_WRONG",
                       f"That code doesn't match. {left} {'try' if left == 1 else 'tries'} left")
        now = datetime.now(UTC)
        return await self._move(order, "delivered", actor, extra={
            "actual_delivery_time": now, "delivery_proof": {"method": "pickup_code", "at": now.isoformat()}})

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
            allowed, _ = customer_cancel_window(order.status, order.placed_at, window, datetime.now(UTC))
            if not allowed:
                raise _err(status.HTTP_409_CONFLICT, "CANCEL_WINDOW_PASSED",
                           "The restaurant has started on your order, so it can't be cancelled now. Ask us from the order for help")
        return await self._cancel(order, actor, data.reason, data.note)

    # ── dispatch (called by realtime over the internal API) ──────────────────
    async def assign_rider(self, order_id: uuid.UUID, rider_id: uuid.UUID, batch_id: uuid.UUID | None = None,
                           batch_position: int | None = None) -> Order:
        """A rider accepted the offer. Idempotent for the same rider. For a batch, the
        order's place in it; a later drop-off records the city's batch bonus (item 2)."""
        order = await self._locked(order_id)
        if order is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
        if order.driver_id == rider_id:
            return order
        if order.driver_id is not None:
            raise _err(status.HTTP_409_CONFLICT, "ALREADY_ASSIGNED", "Another delivery partner has this order")
        if order.status not in ("accepted", "preparing", "almost_ready", "ready"):
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"Can't assign a delivery partner to a {order.status} order")
        order.driver_id, order.rider_assigned_at = rider_id, datetime.now(UTC)
        if batch_id is not None and batch_position:
            order.batch_id, order.batch_position = batch_id, batch_position
            if batch_position >= 2:
                from core_api.modules.rules.service.resolver import Context
                from core_api.modules.rules.service.rules import RuleService

                city = order.market_city or ""
                bonus = (await RuleService(self.db).resolve(Context(country=city[:2], region=city[:5], city=city))).get("rider_pay:batch_bonus")
                order.batch_bonus = Decimal(str(bonus.params["per_extra_order"])) if bonus else Decimal(0)
        await self.db.flush()
        from core_api.modules.identity.service.profile import user_profile

        profile = await user_profile(self.db, rider_id) or {}
        await outbox.add(self.db, "driver.assigned", "order", order.id,
                         _event_payload(order, driver_name=profile.get("name", "your delivery partner")), SOURCE)
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

    async def _cancel(self, order: Order, actor: str, reason: str, note: str | None, paid: bool | None = None) -> Order:
        """``paid``: the payment has just been captured (R27), so it is refunded whatever the status says."""
        was_paid = order.status in sm.PAID_STATES if paid is None else paid
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
