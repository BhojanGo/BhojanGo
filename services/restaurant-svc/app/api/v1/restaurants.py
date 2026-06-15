import math
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_admin, require_owner_or_admin
from app.core.cache import cache_delete_pattern, cache_get, cache_set
from app.db.base import get_db
from app.repositories.restaurant import MenuItemRepository, RestaurantRepository, ReviewRepository
from app.schemas.restaurant import (
    DeliveryCheckResponse,
    MenuItemCreateRequest,
    MenuItemResponse,
    MenuItemUpdateRequest,
    PricingConfigRequest,
    RestaurantCreateRequest,
    RestaurantListResponse,
    RestaurantMenuResponse,
    RestaurantResponse,
    RestaurantUpdateRequest,
    ReviewCreateRequest,
    ReviewResponse,
    SearchRequest,
)
from app.services import geo, search as search_svc

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])
logger = structlog.get_logger(__name__)

CACHE_KEY_LIST = "restaurants:list:{city}:{cuisine}:{page}:{limit}"
CACHE_KEY_RESTAURANT = "restaurants:{id}"


@router.get("", response_model=RestaurantListResponse)
async def list_restaurants(
    city: str | None = Query(None),
    cuisine: str | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=5),
    max_delivery_fee: float | None = Query(None, ge=0),
    is_open: bool | None = Query(None),
    country: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RestaurantListResponse:
    cache_key = f"restaurants:list:{city}:{cuisine}:{country}:{min_rating}:{max_delivery_fee}:{is_open}:{page}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return RestaurantListResponse(**cached)

    repo = RestaurantRepository(db)
    restaurants, total = await repo.list_restaurants(
        city=city,
        cuisine=cuisine,
        min_rating=min_rating,
        max_delivery_fee=max_delivery_fee,
        is_open=is_open,
        country=country,
        page=page,
        limit=limit,
    )

    response = RestaurantListResponse(
        items=[RestaurantResponse.model_validate(r) for r in restaurants],
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total else 0,
    )
    await cache_set(cache_key, response.model_dump(), ttl=300)
    return response


@router.get("/search", response_model=RestaurantListResponse)
async def search_restaurants(
    q: str | None = Query(None),
    city: str | None = Query(None),
    cuisine: str | None = Query(None),
    min_rating: float | None = Query(None),
    is_open: bool | None = Query(None),
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RestaurantListResponse:
    try:
        result = await search_svc.search_restaurants(
            q=q, city=city, cuisine=cuisine, min_rating=min_rating,
            is_open=is_open, lat=lat, lng=lng, page=page, limit=limit,
        )
    except Exception:
        result = {"total": 0, "ids": []}

    if result["ids"]:
        repo = RestaurantRepository(db)
        restaurants: list[Restaurant] = []
        for rid in result["ids"]:
            r = await repo.get_by_id(uuid.UUID(rid))
            if r:
                restaurants.append(r)
        return RestaurantListResponse(
            items=[RestaurantResponse.model_validate(r) for r in restaurants],
            total=result["total"],
            page=page,
            limit=limit,
            total_pages=math.ceil(result["total"] / limit),
        )

    # Fallback: direct DB query when OpenSearch is unavailable or returns empty
    logger.warning("opensearch_fallback", q=q, city=city, cuisine=cuisine)
    repo = RestaurantRepository(db)
    fallback_restaurants, total = await repo.list_restaurants(
        city=city,
        cuisine=cuisine,
        min_rating=min_rating,
        page=page,
        limit=limit,
    )

    # If search text provided, filter by name/description (client-side-ish)
    if q:
        q_lower = q.lower()
        filtered = [
            r for r in fallback_restaurants
            if q_lower in r.name.lower()
            or q_lower in r.description.lower()
            or any(q_lower in ct.lower() for ct in r.cuisine_types)
        ]
        total = len(filtered)
        fallback_restaurants = filtered

    return RestaurantListResponse(
        items=[RestaurantResponse.model_validate(r) for r in fallback_restaurants],
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total else 0,
    )


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
async def get_restaurant(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    cache_key = f"restaurants:{restaurant_id}"
    cached = await cache_get(cache_key)
    if cached:
        return RestaurantResponse(**cached)

    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    response = RestaurantResponse.model_validate(restaurant)
    await cache_set(cache_key, response.model_dump(), ttl=300)
    return response


@router.get("/{restaurant_id}/menu", response_model=RestaurantMenuResponse)
async def get_restaurant_menu(
    restaurant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RestaurantMenuResponse:
    repo = RestaurantRepository(db)
    restaurant = await repo.get_with_menu(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    from app.schemas.restaurant import MenuCategoryResponse
    categories = [
        MenuCategoryResponse(
            id=cat.id,
            restaurant_id=cat.restaurant_id,
            name=cat.name,
            description=cat.description,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            items=[MenuItemResponse.model_validate(item) for item in cat.items if item.is_available],
        )
        for cat in sorted(restaurant.categories, key=lambda c: c.sort_order)
        if cat.is_active
    ]

    uncategorized = [
        MenuItemResponse.model_validate(item)
        for item in restaurant.menu_items
        if item.category_id is None and item.is_available
    ]

    return RestaurantMenuResponse(
        restaurant=RestaurantResponse.model_validate(restaurant),
        categories=categories,
        uncategorized_items=uncategorized,
    )


@router.post("", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    data: RestaurantCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_owner_or_admin)],
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    repo = RestaurantRepository(db)
    address_dict = data.address.model_dump()
    restaurant = await repo.create(
        owner_id=current_user.id,
        name=data.name,
        description=data.description,
        cuisine_types=data.cuisine_types,
        address=address_dict,
        lat=data.location.lat,
        lng=data.location.lng,
        delivery_time_min=data.delivery_time_min,
        delivery_time_max=data.delivery_time_max,
        minimum_order_amount=data.minimum_order_amount,
        delivery_fee=data.delivery_fee,
        currency=data.currency,
        country=data.country,
        city=data.city,
        opens_at=data.opens_at,
        closes_at=data.closes_at,
        tags=data.tags,
    )

    # Index in OpenSearch
    await search_svc.index_restaurant(
        str(restaurant.id),
        {
            "name": restaurant.name,
            "description": restaurant.description,
            "cuisine_types": restaurant.cuisine_types,
            "city": restaurant.city,
            "country": restaurant.country,
            "rating": restaurant.rating,
            "is_open": restaurant.is_open,
            "delivery_fee": float(restaurant.delivery_fee),
            "location": {"lat": restaurant.lat, "lon": restaurant.lng} if restaurant.lat else None,
            "tags": restaurant.tags,
        },
    )
    await cache_delete_pattern("restaurants:list:*")
    return RestaurantResponse.model_validate(restaurant)


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
async def update_restaurant(
    restaurant_id: uuid.UUID,
    data: RestaurantUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_owner_or_admin)],
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    if current_user.role not in ("admin", "super_admin") and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")

    update_data = data.model_dump(exclude_none=True)
    updated = await repo.update(restaurant_id, **update_data)
    await cache_delete_pattern(f"restaurants:{restaurant_id}")
    await cache_delete_pattern("restaurants:list:*")
    return RestaurantResponse.model_validate(updated)


@router.put("/{restaurant_id}/pricing", response_model=RestaurantResponse)
async def configure_pricing(
    restaurant_id: uuid.UUID,
    data: PricingConfigRequest,
    current_user: Annotated[CurrentUser, Depends(require_owner_or_admin)],
    db: AsyncSession = Depends(get_db),
) -> RestaurantResponse:
    """Configure a restaurant's commission / fee model (restaurant-friendly pricing)."""
    missing = data.require_fields_for_model()
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=missing)

    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if current_user.role not in ("admin", "super_admin") and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")

    values: dict = {"pricing_model": data.pricing_model}
    if data.commission_rate is not None:
        values["commission_rate"] = data.commission_rate
    if data.flat_fee_per_order is not None:
        values["flat_fee_per_order"] = data.flat_fee_per_order
    if data.monthly_subscription_fee is not None:
        values["monthly_subscription_fee"] = data.monthly_subscription_fee

    updated = await repo.update(restaurant_id, **values)
    await cache_delete_pattern(f"restaurants:{restaurant_id}")
    await cache_delete_pattern("restaurants:list:*")
    return RestaurantResponse.model_validate(updated)


@router.get("/{restaurant_id}/delivery-check", response_model=DeliveryCheckResponse)
async def delivery_check(
    restaurant_id: uuid.UUID,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
) -> DeliveryCheckResponse:
    """Hyper-local radius check: can this restaurant deliver to the given point?"""
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if restaurant.lat is None or restaurant.lng is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Restaurant location is not configured",
        )

    radius_km = float(restaurant.delivery_radius_km)
    distance_km = round(geo.haversine_km(restaurant.lat, restaurant.lng, lat, lng), 3)
    deliverable = distance_km <= radius_km
    return DeliveryCheckResponse(
        deliverable=deliverable,
        distance_km=distance_km,
        radius_km=radius_km,
        is_long_distance=deliverable and geo.is_long_distance(distance_km, radius_km),
        delivery_fee=float(restaurant.delivery_fee),
        currency=restaurant.currency,
    )


@router.post("/{restaurant_id}/menu-items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    restaurant_id: uuid.UUID,
    data: MenuItemCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_owner_or_admin)],
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if current_user.role not in ("admin", "super_admin") and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")

    item_repo = MenuItemRepository(db)
    item = await item_repo.create(restaurant_id=restaurant_id, **data.model_dump())
    return MenuItemResponse.model_validate(item)


@router.put("/{restaurant_id}/menu-items/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    data: MenuItemUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_owner_or_admin)],
    db: AsyncSession = Depends(get_db),
) -> MenuItemResponse:
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if current_user.role not in ("admin", "super_admin") and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")

    item_repo = MenuItemRepository(db)
    item = await item_repo.update(item_id, **data.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    return MenuItemResponse.model_validate(item)


@router.delete("/{restaurant_id}/menu-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(require_owner_or_admin)],
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if current_user.role not in ("admin", "super_admin") and restaurant.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")

    item_repo = MenuItemRepository(db)
    deleted = await item_repo.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")


@router.post("/{restaurant_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    restaurant_id: uuid.UUID,
    data: ReviewCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    review_repo = ReviewRepository(db)
    existing = await review_repo.get_by_order_id(data.order_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Review already submitted for this order")

    review = await review_repo.create(
        restaurant_id=restaurant_id,
        order_id=data.order_id,
        customer_id=current_user.id,
        customer_name=current_user.email,
        rating=data.rating,
        comment=data.comment,
        food_rating=data.food_rating,
        delivery_rating=data.delivery_rating,
    )

    # Recalculate restaurant rating
    rest_repo = RestaurantRepository(db)
    await rest_repo.update_rating(restaurant_id)
    await cache_delete_pattern(f"restaurants:{restaurant_id}")
    return ReviewResponse.model_validate(review)


@router.post(
    "/{restaurant_id}/approve",
    response_model=RestaurantResponse,
    dependencies=[Depends(require_admin)],
)
async def approve_restaurant(
    restaurant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RestaurantResponse:
    """Admin: Approve a pending restaurant, making it visible to customers."""
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if restaurant.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Restaurant is already '{restaurant.status}', not pending approval",
        )
    updated = await repo.update(restaurant_id, status="active")
    logger.info("restaurant_approved", restaurant_id=str(restaurant_id))
    return RestaurantResponse.model_validate(updated)


@router.post(
    "/{restaurant_id}/reject",
    response_model=RestaurantResponse,
    dependencies=[Depends(require_admin)],
)
async def reject_restaurant(
    restaurant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RestaurantResponse:
    """Admin: Reject a pending restaurant."""
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if restaurant.status not in ("pending_approval", "active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Restaurant cannot be rejected from '{restaurant.status}' status",
        )
    updated = await repo.update(restaurant_id, status="suspended")
    logger.info("restaurant_rejected", restaurant_id=str(restaurant_id))
    return RestaurantResponse.model_validate(updated)


@router.get(
    "/admin/pending",
    response_model=list[RestaurantResponse],
    dependencies=[Depends(require_admin)],
)
async def list_pending_restaurants(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RestaurantResponse]:
    """Admin: List all restaurants pending approval."""
    repo = RestaurantRepository(db)
    restaurants = await repo.list_pending_restaurants(limit=limit, offset=offset)
    return [RestaurantResponse.model_validate(r) for r in restaurants]
