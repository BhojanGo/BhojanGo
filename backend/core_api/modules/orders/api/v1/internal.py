"""Internal order endpoints for realtime (P14). Not for apps: every request must
be signed with INTERNAL_SERVICE_SECRET (shared/internal_auth.py)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.models.order import Order
from core_api.modules.orders.service.order import OrderService
from shared import internal_auth
from shared.db import get_db

router = APIRouter(prefix="/internal/orders", tags=["Internal"], include_in_schema=False)
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


async def signed(request: Request) -> None:
    try:
        internal_auth.verify(request.method, request.url.path, await request.body(),
                             request.headers.get("x-internal-timestamp"), request.headers.get("x-internal-signature"))
    except internal_auth.InternalAuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Internal endpoint")


class AssignRider(BaseModel):
    rider_id: uuid.UUID


async def dispatch_info(db: AsyncSession, order: Order) -> dict:
    from core_api.modules.orders.service.order import business_rules  # noqa: F401  (rules module import)
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    city = order.market_city or ""
    rules = await RuleService(db).resolve(Context(country=city[:2] or None, region=city[:5] or None, city=city or None,
                                                  zone_id=str(order.zone_id) if order.zone_id else None))
    timeout = rules.get("business:dispatch_offer_timeout")
    return {
        "order_id": str(order.id), "status": order.status, "customer_id": str(order.customer_id),
        "restaurant_id": str(order.restaurant_id), "restaurant_name": order.restaurant_name,
        "driver_id": str(order.driver_id) if order.driver_id else None, "market_city": order.market_city,
        "pickup": [order.pickup_lat, order.pickup_lng] if order.pickup_lat is not None else None,
        "dropoff": [order.delivery_lat, order.delivery_lng] if order.delivery_lat is not None else None,
        "offer_timeout_seconds": int(timeout.params["seconds"]) if timeout else 30,
        "distance_unit": "mi" if city.startswith("US") else "km",
    }


@router.get("/{order_id}/dispatch", dependencies=[Depends(signed)])
async def get_dispatch(order_id: uuid.UUID, db: DB) -> dict:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return await dispatch_info(db, order)


@router.post("/{order_id}/assign-rider", dependencies=[Depends(signed)])
async def assign_rider(order_id: uuid.UUID, data: AssignRider, db: DB) -> dict:
    order = await OrderService(db).assign_rider(order_id, data.rider_id)
    return await dispatch_info(db, order)
