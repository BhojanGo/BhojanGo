import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PaymentProvider = Literal["stripe", "razorpay", "wallet"]
PaymentStatus = Literal["pending", "processing", "succeeded", "failed", "cancelled", "refunded", "partially_refunded"]
Currency = Literal["USD", "INR"]


class PaymentInitiateRequest(BaseModel):
    order_id: uuid.UUID
    payment_method_type: Literal["card", "upi", "net_banking", "wallet"]
    payment_method_id: str | None = None
    country: Literal["US", "IN"] = "US"
    amount: int = Field(gt=0, description="Amount in smallest unit (cents/paise)")
    currency: Currency


class PaymentInitiateResponse(BaseModel):
    payment_intent_id: str
    provider: PaymentProvider
    client_secret: str | None = None        # Stripe
    razorpay_order_id: str | None = None    # Razorpay
    amount: int
    currency: Currency


class PaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    provider_payment_id: str
    amount: int
    currency: str
    status: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class WalletBalanceResponse(BaseModel):
    model_config = {"from_attributes": True}

    user_id: uuid.UUID
    balance: float
    currency: str
    updated_at: datetime


class WalletTransactionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    amount: float
    currency: str
    balance_after: float
    description: str
    reference_id: str | None
    reference_type: str | None
    created_at: datetime


class WalletTopupRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: Currency
    payment_method_id: str


class RefundRequest(BaseModel):
    amount: int | None = Field(default=None, gt=0, description="Partial refund amount in cents/paise; omit for full refund")
    reason: str = Field(min_length=1)
    refund_to: Literal["original_payment", "wallet"] = "original_payment"


class RefundResponse(BaseModel):
    refund_id: str
    order_id: str
    amount: int
    currency: str
    status: Literal["pending", "succeeded", "failed"]
    refund_to: str
    created_at: str


class WalletTransactionListResponse(BaseModel):
    items: list[WalletTransactionResponse]
    total: int
    page: int
    limit: int
