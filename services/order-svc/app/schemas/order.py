import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OrderStatus = Literal[
    "pending", "confirmed", "preparing", "ready_for_pickup",
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
