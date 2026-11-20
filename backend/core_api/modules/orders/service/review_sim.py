"""R20: the app store review order's kitchen and delivery partner.

An Apple or Google reviewer signs in with the review customer (tools/review_accounts.py)
and orders from the review kitchen in the hidden review-only city: the order costs
nothing and is placed at once (pricing engine ``review``, payments
``place_review_order``). Nobody works that kitchen or rides there, so the worker's
review simulator (worker app/demo_sim/review.py, REVIEW_SIM=1, allowed in production)
plays them, one step at a time, through the signed POST
/internal/review/orders/{id}/step. Each step is an ordinary transition (OrderService:
status history, outbox events, push to the customer), made as the kitchen or as the
review delivery partner.

It refuses (404) every order that isn't a review order: the order's city must be
review-only, and both its customer and its kitchen's owner must be that city's review
accounts. So a real order can never be moved this way, whatever the worker asks.
"""
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.models.order import Order
from core_api.modules.orders.service.order import OrderService, _err, delivery_eta

Step = Literal["accept", "prepare", "assign", "ready", "pick_up", "deliver"]

# step -> (the states it moves from, the state it moves to, who makes the move)
MOVES: dict[str, tuple[frozenset[str], str, str]] = {
    "accept": (frozenset({"placed"}), "accepted", "restaurant"),
    "prepare": (frozenset({"accepted"}), "preparing", "restaurant"),
    "ready": (frozenset({"preparing", "almost_ready"}), "ready", "restaurant"),
    "pick_up": (frozenset({"ready"}), "picked_up", "rider"),
    "deliver": (frozenset({"picked_up"}), "delivered", "rider"),
}
ASSIGN_FROM = frozenset({"accepted", "preparing", "almost_ready", "ready"})


async def review_settings(db: AsyncSession, order: Order) -> dict | None:
    """The city's settings when this is a review order (a review account's order from a
    kitchen a review account owns, in a review-only city), else None."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.markets.service import review

    settings = await review.city_settings(db, order.market_city)
    if not review.is_review_account(settings, order.customer_id):
        return None
    owner = (await db.execute(select(Restaurant.owner_id).where(Restaurant.id == order.restaurant_id))).scalar()
    return settings if review.is_review_account(settings, owner) else None


async def review_rider(db: AsyncSession, settings: dict) -> uuid.UUID | None:
    """The city's review delivery partner (a review account with the driver role)."""
    from core_api.modules.identity.models.user import User
    from core_api.modules.markets.service.review import REVIEW_ACCOUNTS

    ids = []
    for a in settings.get(REVIEW_ACCOUNTS) or []:
        try:
            ids.append(uuid.UUID(str(a)))
        except ValueError:
            continue
    if not ids:
        return None
    return (await db.execute(select(User.id).where(User.id.in_(ids), User.role == "driver", User.is_active)
                             .order_by(User.created_at))).scalars().first()


async def step(db: AsyncSession, order_id: uuid.UUID, what: Step) -> Order:
    svc = OrderService(db)
    order = await svc._locked(order_id)
    settings = await review_settings(db, order) if order is not None else None
    if order is None or settings is None:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Order not found")
    if what == "assign":
        if order.status not in ASSIGN_FROM:
            raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"Can't assign a delivery partner to a {order.status} order")
        rider = order.driver_id or await review_rider(db, settings)
        if rider is None:
            raise _err(status.HTTP_409_CONFLICT, "NO_REVIEW_RIDER", "The review city has no review delivery partner")
        return await svc.assign_rider(order.id, rider)
    sources, new, actor = MOVES[what]
    if order.status not in sources:
        raise _err(status.HTTP_409_CONFLICT, "ORDER_STATE_INVALID", f"Can't {what.replace('_', ' ')} a {order.status} order")
    if actor == "rider" and order.driver_id is None:
        raise _err(status.HTTP_409_CONFLICT, "NO_RIDER", "No delivery partner is on this order yet")
    now = datetime.now(UTC)
    extra: dict = {}
    if new == "accepted":
        prep = order.estimated_prep_minutes
        extra = {"restaurant_accepted_at": now, "accept_due_at": None,
                 "estimated_delivery_time": delivery_eta(prep or 0, (order.pickup_lat, order.pickup_lng),
                                                         (order.delivery_lat, order.delivery_lng), now)}
    elif new == "ready":
        extra = {"actual_ready_at": now}
    elif new == "picked_up":
        extra = {"picked_up_at": now}
    elif new == "delivered":
        extra = {"actual_delivery_time": now, "delivery_proof": {"method": "review", "at": now.isoformat()}}
    return await svc._move(order, new, actor, extra=extra)
