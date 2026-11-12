"""Rider GPS, ETA and manual assignment (P14)."""
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.schemas.delivery import DeliveryAssignRequest, DriverLocationResponse, DriverLocationUpdateRequest, EtaResponse
from app.services import dispatch
from app.services.core_api import CoreApiError, core_api
from shared import authz

router = APIRouter(prefix="/delivery", tags=["Delivery"])
logger = structlog.get_logger(__name__)


def can_see(user: CurrentUser, info: dict) -> bool:
    """The customer, the assigned rider, or an admin for the order's city."""
    if user.user_id in (info.get("customer_id"), info.get("driver_id")):
        return True
    city = info.get("market_city") or ""
    return bool(city) and authz.can([authz.Assignment.parse(a) for a in user.admin], "orders.view", city)


@router.post("/driver/location", response_model=DriverLocationResponse)
async def update_driver_location(
    data: DriverLocationUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DriverLocationResponse:
    """A rider's GPS fix (every few seconds while online). Goes to the order
    they are delivering, never to one they aren't assigned to."""
    if current_user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")
    state = await dispatch.rider_state(current_user.user_id)
    busy_with = state.get("order_id") if state.get("status") == "busy" else None
    if data.order_id and data.order_id != busy_with:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You aren't delivering that order")
    fix = await dispatch.update_location(current_user.user_id, data.lat, data.lng,
                                         {"heading": data.heading, "speed": data.speed, "accuracy": data.accuracy})
    return DriverLocationResponse(**{**fix, "order_id": busy_with})


@router.get("/driver/active-order")
async def get_driver_active_order(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    if current_user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")
    state = await dispatch.rider_state(current_user.user_id)
    order = state.get("order_id") if state.get("status") == "busy" else None
    return {"driver_id": current_user.user_id, "active_order_id": order, "state": state.get("status", "offline"),
            "location": await dispatch.last_fix(current_user.user_id),
            "order": await dispatch.order_info(order) if order else None}


@router.post("/assign")
async def assign_driver(data: DeliveryAssignRequest, current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    """Manual dispatch: an admin with dispatch.edit for the order's city gives it to a rider."""
    order, rider = str(data.order_id), str(data.driver_id)
    info = await dispatch.order_info(order, refresh=True)
    if info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not authz.can([authz.Assignment.parse(a) for a in current_user.admin], "dispatch.edit", info.get("market_city") or "*"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You need dispatch.edit for this city")
    try:
        await core_api.assign_rider(order, rider)
    except CoreApiError as e:
        raise HTTPException(status_code=e.status, detail=e.args[0])
    r = await dispatch.get_redis()
    await r.hset(dispatch.state_key(rider), mapping={"status": "busy", "order_id": order})
    await r.srem(dispatch.ACTIVE, order)
    await r.zrem(dispatch.RETRY, order)
    logger.info("rider_assigned_manually", order_id=order, rider_id=rider, by=current_user.user_id)
    return {"order_id": order, "driver_id": rider, "status": "assigned"}


@router.get("/{order_id}/eta", response_model=EtaResponse)
async def get_order_eta(order_id: uuid.UUID, current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> EtaResponse:
    """Minutes to pickup and drop-off from the rider's last position."""
    info = await dispatch.order_info(str(order_id))
    if info is None or not can_see(current_user, info):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    fix = await dispatch.last_fix(info["driver_id"]) if info.get("driver_id") else None
    eta = dispatch.eta_for(info, (fix["lat"], fix["lng"])) if fix else None
    return EtaResponse(
        order_id=str(order_id),
        driver_lat=fix["lat"] if fix else None,
        driver_lng=fix["lng"] if fix else None,
        estimated_pickup_minutes=eta["to_pickup_minutes"] if eta else None,
        estimated_delivery_minutes=eta["to_customer_minutes"] if eta else None,
        estimated_delivery_time=eta["arrives_at"] if eta else None,
    )
