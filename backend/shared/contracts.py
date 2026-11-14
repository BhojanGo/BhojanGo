"""Contracts between our own services (P22).

What core_api's internal endpoints return to realtime, as one typed model both
sides import: core_api validates its responses against it, and a contract test
(core_api/modules/orders/tests/test_contract.py) checks that every field
realtime reads is declared here and every core path realtime calls exists.
"""
from pydantic import BaseModel, ConfigDict


class DispatchInfo(BaseModel):
    """An order as dispatch sees it (GET /internal/orders/{id}/dispatch, POST .../assign-rider)."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    status: str
    customer_id: str
    restaurant_id: str
    restaurant_name: str
    restaurant_owner_id: str | None
    driver_id: str | None
    market_city: str | None
    pickup: list[float] | None  # [lat, lng]
    dropoff: list[float] | None
    offer_timeout_seconds: int
    distance_unit: str  # km | mi
    # What the rider sees on the offer (P18)
    code: str
    currency: str
    rider_pay: str | None
    tip: str
    items_count: int
    bags: int
    ready_in_minutes: int | None
    drop_area: str | None
    batching_live: bool = False  # task 43: the city's business:batching rule says live
    rider_pay_batched: str | None = None  # item 2: this order's pay as a later drop-off of a batch
