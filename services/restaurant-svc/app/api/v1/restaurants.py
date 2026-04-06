import math
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_owner_or_admin
from app.core.cache import cache_delete_pattern, cache_get, cache_set
from app.db.base import get_db
from app.repositories.restaurant import MenuItemRepository, RestaurantRepository, ReviewRepository
from app.schemas.restaurant import (
    MenuItemCreateRequest,
    MenuItemResponse,
    MenuItemUpdateRequest,
    RestaurantCreateRequest,
    RestaurantListResponse,
    RestaurantMenuResponse,
    RestaurantResponse,
    RestaurantUpdateRequest,
    ReviewCreateRequest,
    ReviewResponse,
    SearchRequest,
)
from app.services import search as search_svc

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
    cache_key = f"restaurants:list:{city}:{cuisine}:{country}:{page}:{limit}"
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
    result = await search_svc.search_restaurants(
        q=q, city=city, cuisine=cuisine, min_rating=min_rating,
        is_open=is_open, lat=lat, lng=lng, page=page, limit=limit,
    )
    if not result["ids"]:
        return RestaurantListResponse(items=[], total=0, page=page, limit=limit, total_pages=0)

    repo = RestaurantRepository(db)
    restaurants = []
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
            "delivery_fee": restaurant.delivery_fee,
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
