import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DriverLocationUpdateRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    heading: float | None = Field(default=None, ge=0, le=360)
    speed: float | None = Field(default=None, ge=0)
    accuracy: float | None = Field(default=None, ge=0)
    order_id: str | None = None


class DriverLocationResponse(BaseModel):
    driver_id: str
    order_id: str | None
    lat: float
    lng: float
    heading: float | None
    speed: float | None
    accuracy: float | None
    timestamp: str


class DeliveryAssignRequest(BaseModel):
    order_id: uuid.UUID
    driver_id: uuid.UUID


class EtaResponse(BaseModel):
    order_id: str
    driver_lat: float | None
    driver_lng: float | None
    estimated_pickup_minutes: int | None
    estimated_delivery_minutes: int | None
    estimated_delivery_time: str | None
    route_polyline: str | None = None


class WebSocketMessage(BaseModel):
    type: str  # "location_update" | "status_change" | "eta_update" | "error"
    payload: dict
    timestamp: str
