import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PaymentProvider = Literal["stripe", "razorpay", "wallet", "fake"]
PaymentStatus = Literal["pending", "processing", "succeeded", "failed", "cancelled", "refunded", "partially_refunded"]
Currency = Literal["USD", "INR"]


class PaymentInitiateRequest(BaseModel):
    order_id: uuid.UUID
    payment_method_type: Literal["card", "upi", "net_banking", "wallet"]
    payment_method_id: str | None = None
    # Ignored since P11: the order decides the gateway, amount and currency. If
    # sent, amount and currency must match the order.
    country: Literal["US", "IN"] | None = None
    amount: int | None = Field(default=None, gt=0, description="Optional check, in cents/paise")
    currency: Currency | None = None


class FakeCompleteRequest(BaseModel):
    """Local only. Omit outcome to use the one implied by payment_method_id."""

    outcome: Literal["succeeded", "failed"] | None = None


class PaymentInitiateResponse(BaseModel):
    payment_intent_id: str
    provider: PaymentProvider
    client_secret: str | None = None        # Stripe
    razorpay_order_id: str | None = None    # Razorpay
    amount: int
    currency: Currency
    # What the app's payment SDK needs: Stripe PaymentSheet (cards, Apple Pay,
    # Google Pay), Razorpay Checkout (UPI, cards, wallets), or the local fake.
    checkout: dict | None = None


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RefundItem(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=50)


class ItemRefundRequest(BaseModel):
    items: list[RefundItem] = []
    include_delivery_fee: bool = False
    reason: str = Field(min_length=3, max_length=60, examples=["missing_item"])
    note: str | None = Field(default=None, max_length=500)


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
    amount: int | None = Field(default=None, gt=0, description="Partial refund amount in cents/paise; omit to refund the full remaining amount")
    reason: str = Field(min_length=1)
    refund_to: Literal["original_payment", "wallet"] = "original_payment"
    idempotency_key: str | None = Field(
        default=None,
        max_length=255,
        description="Client-supplied key; retries with the same key return the original refund without re-charging",
    )


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
