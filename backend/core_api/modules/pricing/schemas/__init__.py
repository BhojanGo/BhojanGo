import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class OptionPick(BaseModel):
    group: str = Field(examples=["Add-ons"])
    option: str = Field(examples=["Extra raita"])


class CartItem(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=50)
    options: list[OptionPick] = []


class Where(BaseModel):
    """Deliver to a saved address, or to a point."""

    address_id: uuid.UUID | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def one(self) -> "Where":
        if self.address_id is None and (self.lat is None or self.lng is None):
            raise ValueError("Give address_id, or lat and lng")
        return self


class QuoteRequest(BaseModel):
    restaurant_id: uuid.UUID
    items: list[CartItem] = Field(min_length=1)
    deliver_to: Where
    tip: Decimal = Field(default=Decimal("0"), ge=0)
    promo_code: str | None = Field(default=None, max_length=20)


class BillLineOut(BaseModel):
    code: str
    label: str
    amount: Decimal
    funded_by: str | None = None


class QuoteOut(BaseModel):
    quote_id: uuid.UUID
    token: str = Field(description="Send this when placing the order; valid until expires_at")
    expires_at: datetime
    currency: str
    lines: list[BillLineOut]
    total: Decimal
    tax_pending: bool = Field(description="True when an external tax provider still adds tax (US until P9)")
    zone: str
    city: str
    distance: Decimal
    distance_unit: str


class SplitOut(BaseModel):
    restaurant: Decimal
    rider: Decimal
    tax: Decimal
    platform: Decimal
    detail: dict[str, Decimal]


class SimCart(BaseModel):
    """Either real items from a restaurant's menu, or just a food subtotal."""

    items: list[CartItem] = []
    food_subtotal: Decimal | None = Field(default=None, gt=0)


class SimulateRequest(BaseModel):
    city: str = Field(examples=["IN-TG-HYD"])
    zone_id: uuid.UUID | None = None
    restaurant_id: uuid.UUID | None = None
    cart: SimCart
    distance: Decimal = Field(gt=0, examples=[4.2], description="In the country's unit (km or mi)")
    local_time: datetime = Field(examples=["2026-11-12T20:00:00"], description="City local time; a timezone is ignored")
    tip: Decimal = Field(default=Decimal("0"), ge=0)
    restaurant_tier: str | None = Field(default=None, examples=["B"])
    first_order: bool = False
    promo_code: str | None = None
    draft_rule_ids: list[uuid.UUID] = Field(default=[], description="Drafts to try against what is live now")


class SimSide(BaseModel):
    ok: bool
    message: str | None = None
    lines: list[BillLineOut] = []
    total: Decimal | None = None
    split: SplitOut | None = None
    rules: list[dict] = []


class SimulateOut(BaseModel):
    currency: str
    live: SimSide
    draft: SimSide
    changes: list[dict] = Field(description="Lines and split amounts that differ: {label, live, draft}")
