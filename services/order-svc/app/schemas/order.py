import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OrderStatus = Literal[
    "pending", "confirmed", "preparing", "almost_ready", "ready_for_pickup",
    "picked_up", "delivered", "cancelled"
]
PaymentMethod = Literal["card", "wallet", "upi", "net_banking", "cash_on_delivery"]
CancellationReason = Literal[
    "customer_cancelled", "restaurant_cancelled", "driver_not_found",
    "payment_failed", "item_unavailable", "restaurant_closed", "other"
]


class AddressInput(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str
    lat: float | None = None
    lng: float | None = None
    landmark: str | None = None


class OrderItemCustomizationInput(BaseModel):
    customization_id: str
    option_id: str


class OrderItemInput(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=50)
    customizations: list[OrderItemCustomizationInput] = Field(default=[])


class OrderCreateRequest(BaseModel):
    restaurant_id: uuid.UUID
    items: list[OrderItemInput] = Field(min_length=1)
    delivery_address: AddressInput
    payment_method: PaymentMethod
    special_instructions: str | None = Field(default=None, max_length=500)
    promo_code: str | None = None
    tip: float = Field(default=0.0, ge=0)
    loyalty_points_to_use: int = Field(default=0, ge=0)


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus
    note: str | None = None


class OrderCancelRequest(BaseModel):
    reason: CancellationReason
    note: str | None = Field(default=None, max_length=500)


class OrderItemResponse(BaseModel):
    menu_item_id: str
    name: str
    price: float
    quantity: int
    customizations: list[dict[str, Any]]
    subtotal: float
    image_url: str | None = None


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    customer_id: uuid.UUID
    restaurant_id: uuid.UUID
    restaurant_name: str
    driver_id: uuid.UUID | None
    items: list[dict[str, Any]]
    status: str
    subtotal: float
    delivery_fee: float
    taxes: float
    tip: float
    discount: float
    total: float
    currency: str
    # Pain-point layer: fee transparency + readiness + distance + timeline
    platform_fee: float = 0.0
    restaurant_payout: float = 0.0
    estimated_prep_minutes: int = 20
    restaurant_accepted_at: datetime | None = None
    actual_ready_at: datetime | None = None
    delivery_distance_km: float | None = None
    is_long_distance: bool = False
    status_history: list[dict[str, Any]] = []
    delivery_address: dict[str, Any]
    payment_method: str
    payment_intent_id: str | None
    estimated_delivery_time: datetime | None
    actual_delivery_time: datetime | None
    cancellation_reason: str | None
    cancellation_note: str | None
    special_instructions: str | None
    promo_code: str | None
    loyalty_points_earned: int
    loyalty_points_used: int
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class FeeBreakdown(BaseModel):
    """Customer-facing fee transparency breakdown for a single order."""

    food_subtotal: float
    delivery_fee: float
    platform_fee: float          # platform commission / service revenue for this order
    restaurant_payout: float     # what the restaurant receives (subtotal - platform_fee)
    tip: float
    taxes: float
    discount: float
    total: float                 # amount charged to the customer
    currency: str


class PainPointMetrics(BaseModel):
    """Aggregate pain-point analytics for the admin dashboard."""

    total_orders: int
    total_platform_revenue: float
    long_distance_orders: int
    long_distance_rate: float
    avg_estimated_prep_minutes: float
    avg_delivery_distance_km: float
    orders_by_status: dict[str, int]


class StatusTimelineEntry(BaseModel):
    status: str
    at: str | None = None


class OrderTimelineResponse(BaseModel):
    order_id: uuid.UUID
    status: str
    estimated_prep_minutes: int
    restaurant_accepted_at: datetime | None
    actual_ready_at: datetime | None
    timeline: list[StatusTimelineEntry]
