import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.core.redis import get_driver_location, publish_location_update, store_driver_location
from app.schemas.delivery import (
    DeliveryAssignRequest,
    DriverLocationResponse,
    DriverLocationUpdateRequest,
    EtaResponse,
)
from app.services.dynamodb import record_location_event
from app.services.eta import calculate_eta

router = APIRouter(prefix="/delivery", tags=["Delivery"])
logger = structlog.get_logger(__name__)


@router.post("/driver/location", response_model=DriverLocationResponse)
async def update_driver_location(
    data: DriverLocationUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DriverLocationResponse:
    """Driver updates their GPS position. Stored in Redis with 30s TTL."""
    if current_user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")

    timestamp = datetime.now(UTC).isoformat()
    location_data = {
        "driver_id": str(current_user.id),
        "order_id": data.order_id,
        "lat": data.lat,
        "lng": data.lng,
        "heading": data.heading,
        "speed": data.speed,
        "accuracy": data.accuracy,
        "timestamp": timestamp,
    }

    await store_driver_location(str(current_user.id), location_data)

    # If driver has active order, broadcast to tracking channel
    if data.order_id:
        ws_message = {
            "type": "location_update",
            "payload": location_data,
            "timestamp": timestamp,
        }
        await publish_location_update(data.order_id, ws_message)

        # Record in DynamoDB history
        await record_location_event(
            order_id=data.order_id,
            driver_id=str(current_user.id),
            lat=data.lat,
            lng=data.lng,
        )

    return DriverLocationResponse(**location_data)


@router.get("/driver/active-order")
async def get_driver_active_order(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Driver gets their current active order info."""
    if current_user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")
    location = await get_driver_location(str(current_user.id))
    order_id = location.get("order_id") if location else None
    return {"driver_id": str(current_user.id), "active_order_id": order_id, "location": location}


@router.post("/assign")
async def assign_driver(
    data: DeliveryAssignRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Admin assigns a driver to an order."""
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    # In production: call order-svc to set driver_id on the order
    logger.info("driver_assigned", order_id=str(data.order_id), driver_id=str(data.driver_id))
    await record_location_event(
        order_id=str(data.order_id),
        driver_id=str(data.driver_id),
        lat=0.0,
        lng=0.0,
        event_type="assigned",
    )
    return {"order_id": str(data.order_id), "driver_id": str(data.driver_id), "status": "assigned"}


@router.get("/{order_id}/eta", response_model=EtaResponse)
async def get_order_eta(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> EtaResponse:
    """Get ETA for a specific order."""
    # In production: fetch driver location + restaurant/delivery coords from order-svc
    driver_id_from_order = None  # Would be fetched from order service

    driver_location = None
    if driver_id_from_order:
        driver_location = await get_driver_location(str(driver_id_from_order))

    if not driver_location:
        return EtaResponse(
            order_id=str(order_id),
            driver_lat=None,
            driver_lng=None,
            estimated_pickup_minutes=None,
            estimated_delivery_minutes=None,
            estimated_delivery_time=None,
        )

    eta = await calculate_eta(
        driver_lat=driver_location["lat"],
        driver_lng=driver_location["lng"],
        restaurant_lat=0.0,   # Would be from order data
        restaurant_lng=0.0,
        delivery_lat=0.0,
        delivery_lng=0.0,
    )

    return EtaResponse(
        order_id=str(order_id),
        driver_lat=driver_location["lat"],
        driver_lng=driver_location["lng"],
        **eta,
    )
