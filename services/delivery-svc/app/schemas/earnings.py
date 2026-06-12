from typing import Literal

from pydantic import BaseModel, Field


class ShiftStatusResponse(BaseModel):
    driver_id: str
    online: bool
    status: str | None = None
    available_minutes: int = 0
    active_minutes: int = 0
    waiting_minutes: int = 0


class ShiftActivityRequest(BaseModel):
    status: Literal["available", "active", "waiting", "idle"]


class EarningsEstimateRequest(BaseModel):
    available_minutes: int = Field(ge=0)
    active_minutes: int = Field(ge=0)
    waiting_minutes: int = Field(ge=0)
    miles: float = Field(ge=0, default=0)
    tips: float = Field(ge=0, default=0)
    deductions: float = Field(ge=0, default=0)
    num_orders: int = Field(ge=0, default=1)


class EarningsBreakdownResponse(BaseModel):
    available_minutes: int
    active_minutes: int
    waiting_minutes: int
    miles: float
    num_orders: int
    active_payout: float
    waiting_time_payout: float
    mileage_payout: float
    order_bonus: float
    floor_guarantee: float
    floor_topup: float
    tips: float
    gross_earnings: float
    deductions: float
    net_earnings: float
