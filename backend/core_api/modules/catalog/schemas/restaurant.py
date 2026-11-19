import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from core_api.modules.catalog.service.ratings import RatingDisplay, rating_display


# From Markets, not a list here: catalog's create checks the country is open and the
# currency is the country's (markets.service.countries).
Country = Annotated[str, Field(pattern=r"^[A-Z]{2}$", examples=["IN"])]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$", examples=["INR"])]
RestaurantStatus = Literal["active", "inactive", "pending_approval", "suspended"]
PricingModel = Literal["percentage_commission", "flat_fee_per_order", "monthly_subscription"]

CUISINE_TYPES = [
    "indian", "chinese", "italian", "mexican", "american", "thai", "japanese",
    "mediterranean", "fast_food", "pizza", "burgers", "sushi", "biryani",
    "south_indian", "north_indian", "street_food", "healthy", "desserts",
    "beverages", "other",
]

ALLERGENS = ["gluten", "dairy", "eggs", "nuts", "peanuts", "soy", "shellfish", "fish", "sesame"]


class AddressSchema(BaseModel):
    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip: str = Field(min_length=1)
    country: Country
    lat: float | None = None
    lng: float | None = None
    landmark: str | None = None


class GeoPointSchema(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RestaurantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=2000)
    cuisine_types: list[str] = Field(min_length=1)
    address: AddressSchema
    location: GeoPointSchema
    delivery_time_min: int = Field(ge=5, le=120)
    delivery_time_max: int = Field(ge=10, le=180)
    minimum_order_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_fee: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: Currency
    country: Country
    city: str = Field(min_length=1)
    opens_at: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    closes_at: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    tags: list[str] = Field(default=[])


class RestaurantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    cuisine_types: list[str] | None = None
    logo_url: str | None = None
    cover_url: str | None = None
    is_open: bool | None = None
    opens_at: str | None = None
    closes_at: str | None = None
    delivery_time_min: int | None = Field(default=None, ge=5)
    delivery_time_max: int | None = Field(default=None, ge=10)
    minimum_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    delivery_fee: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    delivery_radius_km: Decimal | None = Field(default=None, gt=0, le=100, max_digits=6, decimal_places=2)
    avg_prep_minutes: int | None = Field(default=None, ge=1, le=240)
    tags: list[str] | None = None
    status: RestaurantStatus | None = None


class PricingConfigRequest(BaseModel):
    """Configure a restaurant's commission / fee model."""

    pricing_model: PricingModel
    flat_fee_per_order: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    monthly_subscription_fee: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    def require_fields_for_model(self) -> str | None:
        """Return an error message if the required field for the chosen model is missing."""
        if self.pricing_model == "flat_fee_per_order" and self.flat_fee_per_order is None:
            return "flat_fee_per_order is required for flat_fee_per_order"
        if self.pricing_model == "monthly_subscription" and self.monthly_subscription_fee is None:
            return "monthly_subscription_fee is required for monthly_subscription"
        return None


class DeliveryCheckResponse(BaseModel):
    deliverable: bool
    distance_km: float
    radius_km: float
    is_long_distance: bool
    delivery_fee: float
    currency: str


class PublicRestaurant(BaseModel):
    """A restaurant as customers and the public see it (browse, search, the
    restaurant page, the menu). Never the commission or payout terms, the
    owner, tax registration or licence documents: those are in
    RestaurantResponse, for the owner and admins only. The FSSAI licence
    number stays: Indian law requires showing it to customers.
    integration/test_public_contract.py fails if a public route grows one."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    slug: str
    description: str
    cuisine_types: list[str]
    logo_url: str | None
    cover_url: str | None  # the kitchen's own photo (what the kitchen app edits)
    # What customers are shown (catalog.service.photos): the cover, else the first dish photo, else the cuisine's library photo.
    photo_url: str | None = None
    address: dict[str, Any]
    lat: float | None
    lng: float | None
    rating: float
    review_count: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rating_display(self) -> RatingDisplay:
        """Public stars: {"new": true} below 5 ratings, else {"new": false, "stars": 4.6, "count": 23}."""
        return rating_display(self.rating, self.review_count)

    is_open: bool
    opens_at: str | None
    closes_at: str | None
    delivery_time_min: int
    delivery_time_max: int
    minimum_order_amount: float
    delivery_fee: float
    delivery_radius_km: float = 5.0
    avg_prep_minutes: int = 20
    currency: str
    country: str
    city: str
    tags: list[str]
    status: str
    is_active: bool
    fssai_number: str | None = None
    paused_reason: str | None = None
    # R17: an admin paused it (an incident): "Closed for now", back by itself at back_at if set. The reason stays with admins.
    closed_for_now: bool = False
    back_at: datetime | None = None
    # The kitchen's city time zone (IANA), on GET /restaurants/by-slug: checkout's "arrives 7:05-7:20" is on its clock.
    time_zone: str | None = None
    created_at: datetime
    updated_at: datetime


class RestaurantResponse(PublicRestaurant):
    """The full restaurant, for its owner and admins (create, update, pricing,
    approve, the admin lists): adds the commission terms, owner and licence expiry."""

    owner_id: uuid.UUID
    # Pain-point layer
    pricing_model: str = "percentage_commission"
    flat_fee_per_order: float = 0.0
    monthly_subscription_fee: float = 0.0
    tier: str | None = None
    fssai_expires_on: date | None = None


class MenuItemCreateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=1000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=100)
    is_veg: bool = False
    is_vegan: bool = False
    allergens: list[str] = Field(default=[])
    customizations: list[dict[str, Any]] = Field(default=[])
    prep_time_minutes: int = Field(default=15, ge=1, le=120)
    calories: int | None = Field(default=None, ge=0)
    sort_order: int = Field(default=0)


class MenuItemUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    category: str | None = None
    is_veg: bool | None = None
    is_available: bool | None = None
    allergens: list[str] | None = None
    customizations: list[dict[str, Any]] | None = None
    image_url: str | None = None
    prep_time_minutes: int | None = None
    calories: int | None = None


class MenuItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    restaurant_id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    description: str
    price: float
    image_url: str | None
    category: str
    is_veg: bool
    is_vegan: bool
    is_available: bool
    allergens: list[str]
    # P10: real option groups with min/max picks; ``customizations`` is the same
    # data in the pre-P10 shape for apps that still read it.
    option_groups: list[dict[str, Any]] = []
    customizations: list[dict[str, Any]] = []
    sold_out_today: bool = False
    sort_order: int
    prep_time_minutes: int
    calories: int | None
    created_at: datetime
    updated_at: datetime


class MenuCategoryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    description: str | None
    sort_order: int
    is_active: bool
    items: list[MenuItemResponse] = []


class RestaurantMenuResponse(BaseModel):
    restaurant: PublicRestaurant
    categories: list[MenuCategoryResponse]
    uncategorized_items: list[MenuItemResponse]


class ReviewCreateRequest(BaseModel):
    order_id: uuid.UUID
    rating: float = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    food_rating: float | None = Field(default=None, ge=1, le=5)
    delivery_rating: float | None = Field(default=None, ge=1, le=5)


class ReviewResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    restaurant_id: uuid.UUID
    order_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    customer_avatar: str | None
    rating: float
    comment: str | None
    food_rating: float | None
    delivery_rating: float | None
    created_at: datetime


class PublicRestaurantList(BaseModel):
    items: list[PublicRestaurant]
    total: int
    page: int
    limit: int
    total_pages: int


class RestaurantListResponse(BaseModel):
    """Admins' list (full restaurants)."""

    items: list[RestaurantResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class SearchRequest(BaseModel):
    q: str | None = None
    city: str | None = None
    cuisine: str | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)
    max_delivery_fee: float | None = None
    is_open: bool | None = None
    is_veg: bool | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    lat: float | None = None
    lng: float | None = None
