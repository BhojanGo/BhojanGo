"""Saved payment methods: GET/POST /me/payment-methods, DELETE and default."""
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import get_current_active_user
from core_api.modules.identity.models.user import User
from core_api.modules.payments.models.payment_method import PaymentMethod
from core_api.modules.payments.service import methods
from shared.db import get_db

router = APIRouter(prefix="/me/payment-methods", tags=["Payment methods"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[User, Depends(get_current_active_user)]


class PaymentMethodCreate(BaseModel):
    """A card the provider's own form tokenised. Send the token and the display
    details the provider returned, never the card number."""

    model_config = {"extra": "forbid"}

    provider: Literal["stripe", "razorpay", "fake"]
    provider_token: str = Field(max_length=255, examples=["pm_1QaBcDeFgHiJkLmN"])
    brand: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z][A-Za-z _-]*$", examples=["visa"])
    last4: str = Field(pattern=r"^\d{4}$", examples=["4242"])
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=2000, le=2100)
    is_default: bool = False

    @model_validator(mode="before")
    @classmethod
    def _no_card_numbers(cls, data: Any) -> Any:
        if methods.looks_like_card_number(data):
            raise ValueError("Never send a card number: send the provider's token (pm_..., token_...) instead")
        return data

    @model_validator(mode="after")
    def _token_and_expiry(self) -> "PaymentMethodCreate":
        if not methods.TOKEN_FORMAT[self.provider].match(self.provider_token):
            want = {"stripe": "pm_...", "razorpay": "token_...", "fake": "pm_fake_..."}[self.provider]
            raise ValueError(f"A {self.provider} token looks like {want}")
        if methods.is_expired(self.exp_month, self.exp_year):
            raise ValueError("This card has expired")
        self.brand = self.brand.lower()
        return self


class PaymentMethodOut(BaseModel):
    id: uuid.UUID
    provider: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime


async def _own(db: AsyncSession, user: User, method_id: uuid.UUID) -> PaymentMethod:
    m = await db.get(PaymentMethod, method_id)
    if m is None or m.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    return m


@router.get("", response_model=list[PaymentMethodOut])
async def list_payment_methods(me: Me, db: DB) -> list[PaymentMethodOut]:
    """Your saved cards (brand, last four, expiry; the token never leaves the server)."""
    return [PaymentMethodOut(**methods.as_dict(m)) for m in await methods.list_for(db, me.id)]


@router.post("", response_model=PaymentMethodOut, status_code=status.HTTP_201_CREATED)
async def add_payment_method(data: PaymentMethodCreate, me: Me, db: DB) -> PaymentMethodOut:
    """Save a tokenised card. The first one becomes the default."""
    existing = await methods.list_for(db, me.id)
    if any(m.provider == data.provider and m.provider_token == data.provider_token for m in existing):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "ALREADY_SAVED", "message": "This card is already saved"})
    m = PaymentMethod(user_id=me.id, provider=data.provider, provider_token=data.provider_token, brand=data.brand,
                      last4=data.last4, exp_month=data.exp_month, exp_year=data.exp_year, is_default=False)
    db.add(m)
    await db.flush()
    if data.is_default or not existing:
        await methods.make_default(db, m)
    await db.refresh(m)
    return PaymentMethodOut(**methods.as_dict(m))


@router.delete("/{payment_method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment_method(payment_method_id: uuid.UUID, me: Me, db: DB) -> None:
    await methods.remove(db, await _own(db, me, payment_method_id))


@router.post("/{payment_method_id}/default", response_model=PaymentMethodOut)
async def set_default_payment_method(payment_method_id: uuid.UUID, me: Me, db: DB) -> PaymentMethodOut:
    m = await _own(db, me, payment_method_id)
    await methods.make_default(db, m)
    await db.refresh(m)
    return PaymentMethodOut(**methods.as_dict(m))

