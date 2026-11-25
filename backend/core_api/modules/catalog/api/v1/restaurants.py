import math
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.service import menu as menu_svc
from core_api.modules.catalog.service import menu_edit as edit
from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.catalog.service import access
from shared import authz
from shared.auth import optional_viewer
from shared.cache_versions import VersionedCache
from core_api.modules.catalog.repository.cache import cache_delete_pattern, cache_get, cache_set
from shared.db import get_db
from core_api.modules.catalog.repository.restaurant import MenuItemRepository, RestaurantRepository, ReviewRepository
from core_api.modules.catalog.schemas.restaurant import (
    DeliveryCheckResponse,
    MenuItemCreateRequest,
    MenuItemResponse,
    MenuItemUpdateRequest,
    PricingConfigRequest,
    PublicRestaurant,
    PublicRestaurantList,
    RestaurantCreateRequest,
    RestaurantListResponse,
    RestaurantMenuResponse,
    RestaurantResponse,
    RestaurantUpdateRequest,
    ReviewCreateRequest,
    ReviewResponse,
    SearchRequest,
)
from core_api.modules.catalog.service import geo, search as search_svc
from core_api.modules.catalog.service.photos import photos_for

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])
logger = structlog.get_logger(__name__)

# Whoever is looking at a public route, if signed in (R19: review accounts see their review-only city's kitchen).
Looker = Annotated[uuid.UUID | None, Depends(optional_viewer)]

CACHE_KEY_LIST = "restaurants:list:{city}:{cuisine}:{page}:{limit}"
CACHE_KEY_RESTAURANT = "restaurants:{id}"


async def _hidden(db: AsyncSession, viewer: uuid.UUID | None = None):  # type: ignore[no-untyped-def]
    """The review-only cities (R19) this viewer may not see: their kitchens are left out or 404."""
    from core_api.modules.markets.service import review

    return await review.hidden_for(db, viewer)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")


async def _public(db: AsyncSession, restaurants: list) -> list[PublicRestaurant]:  # type: ignore[type-arg]
    """Public kitchens with the photo customers are shown (photo_url: catalog.service.photos)."""
    shown = await photos_for(db, restaurants)
    out = [PublicRestaurant.model_validate(r) for r in restaurants]
    for p in out:
        p.photo_url = shown.get(str(p.id))
    return out


@router.get("", response_model=PublicRestaurantList)
async def list_restaurants(
    city: str | None = Query(None),
    cuisine: str | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=5),
    max_delivery_fee: float | None = Query(None, ge=0),
    is_open: bool | None = Query(None),
    country: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PublicRestaurantList:
    cache_key = f"restaurants:list:{city}:{cuisine}:{country}:{page}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return PublicRestaurantList(**cached)

    repo = RestaurantRepository(db)
    restaurants, total = await repo.list_restaurants(
        exclude=(await _hidden(db)).names,  # R19: never the store reviewers' kitchen
        city=city,
        cuisine=cuisine,
        min_rating=min_rating,
        max_delivery_fee=max_delivery_fee,
        is_open=is_open,
        country=country,
        page=page,
        limit=limit,
    )

    response = PublicRestaurantList(
        items=await _public(db, restaurants),
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total else 0,
    )
    await cache_set(cache_key, response.model_dump(), ttl=300)
    return response


@router.get("/search", response_model=PublicRestaurantList)
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
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PublicRestaurantList:
    result = await search_svc.search_restaurants(
        q=q, city=city, cuisine=cuisine, min_rating=min_rating,
        is_open=is_open, lat=lat, lng=lng, page=page, limit=limit,
    )
    if not result["ids"]:
        return PublicRestaurantList(items=[], total=0, page=page, limit=limit, total_pages=0)

    repo = RestaurantRepository(db)
    hidden = await _hidden(db)
    restaurants = []
    for rid in result["ids"]:
        r = await repo.get_by_id(uuid.UUID(rid))
        if r and not hidden.kitchen(r.country, r.city):  # R19: never the store reviewers' kitchen
            restaurants.append(r)

    return PublicRestaurantList(
        items=await _public(db, restaurants),
        total=result["total"],
        page=page,
        limit=limit,
        total_pages=math.ceil(result["total"] / limit),
    )


@router.get("/by-slug/{slug}", response_model=PublicRestaurant)
async def get_restaurant_by_slug(slug: str, db: AsyncSession = Depends(get_db, scope="function")) -> PublicRestaurant:
    """A live restaurant by its URL slug (the web's restaurant pages, P20)."""
    from sqlalchemy import select

    from core_api.modules.catalog.models.restaurant import Restaurant

    r = (await db.execute(select(Restaurant).where(
        Restaurant.slug == slug, Restaurant.status == "active", Restaurant.deleted_at.is_(None)))).scalars().first()
    if r is None or (await _hidden(db)).kitchen(r.country, r.city):  # R19: the website never shows the reviewers' kitchen
        raise _not_found()
    from core_api.modules.catalog.service.menu import restaurant_market

    out = (await _public(db, [r]))[0]
    out.time_zone = str((await restaurant_market(db, r))[1])
    return out


@router.get("/{restaurant_id}", response_model=PublicRestaurant)
async def get_restaurant(
    restaurant_id: uuid.UUID,
    viewer: Looker,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PublicRestaurant:
    """A kitchen. In a review-only city (R19): 404 except for its review accounts
    (checked before the cache, so a cached copy never reaches anyone else)."""
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_id(restaurant_id)
    if not restaurant or (await _hidden(db, viewer)).kitchen(restaurant.country, restaurant.city):
        raise _not_found()
    cache_key = f"restaurants:{restaurant_id}"
    cached = await cache_get(cache_key)
    if cached:
        return PublicRestaurant(**cached)

    response = (await _public(db, [restaurant]))[0]
    await cache_set(cache_key, response.model_dump(), ttl=300)
    return response


@router.get("/{restaurant_id}/menu", response_model=RestaurantMenuResponse)
async def get_restaurant_menu(
    restaurant_id: uuid.UUID,
    viewer: Looker,
    db: AsyncSession = Depends(get_db, scope="function"),
) -> RestaurantMenuResponse:
    """The menu with option groups (min/max picks, prices) and what is sold out today.
    In a review-only city (R19): 404 except for its review accounts."""
    # R22: half of all requests at a dinner rush. The answer is the same for everyone who
    # may see the kitchen, so its JSON is kept in each process until the kitchen or its menu,
    # options or hours change (``kitchen:<id>`` version, shared/cache_versions.py), or until
    # the first sold-out-today item comes back (at most MENU_CACHE_SECONDS). Who may see it
    # (review cities) is still checked for each viewer, before the cached answer is used.
    from shared import cache_versions as cv

    if not cv.enabled():
        return (await _menu(db, restaurant_id, viewer))[2]
    ver = await cv.versions(db, cv.kitchen_scopes(restaurant_id))
    hit = _menus.get(restaurant_id, ver)
    if not cv.VersionedCache.is_miss(hit):
        country, city, body = hit
        if (await _hidden(db, viewer)).kitchen(country, city):
            raise _not_found()
        return Response(body, media_type="application/json")  # type: ignore[return-value]
    country, city, menu, until = await _menu(db, restaurant_id, viewer)
    body = menu.model_dump_json().encode()
    _menus.put(db, restaurant_id, ver, (country, city, body), ttl=until)
    return Response(body, media_type="application/json")  # type: ignore[return-value]


MENU_CACHE_SECONDS = 300.0
_menus = VersionedCache("catalog.menu", ttl=MENU_CACHE_SECONDS, size=2048)


async def _menu(db: AsyncSession, restaurant_id: uuid.UUID, viewer: uuid.UUID | None):  # type: ignore[no-untyped-def]
    """(country, city, the menu, seconds it may be kept) or 404."""
    from datetime import UTC, datetime

    repo = RestaurantRepository(db)
    restaurant = await repo.get_with_menu(restaurant_id)
    if not restaurant or (await _hidden(db, viewer)).kitchen(restaurant.country, restaurant.city):
        raise _not_found()
    now = datetime.now(UTC)
    # "Sold out today" ends at the kitchen's midnight: keep the answer no longer than that.
    ends = [i.sold_out_until for i in restaurant.menu_items if i.sold_out_until is not None and i.sold_out_until > now]
    local = now.astimezone((await menu_svc.restaurant_market(db, restaurant))[1])
    # R43: nor past the next time a dish or category schedule starts or ends ("available_now")
    windows = [(x.available_from, x.available_until) for x in [*restaurant.menu_items, *restaurant.categories]
               if x.available_from is not None and x.available_until is not None]
    edge = edit.seconds_to_next_edge(windows, local)
    until = min([MENU_CACHE_SECONDS, *((e - now).total_seconds() for e in ends), *([edge] if edge else [])])
    return restaurant.country, restaurant.city, await _menu_out(db, restaurant, local), until


async def _menu_out(db: AsyncSession, restaurant, local=None) -> RestaurantMenuResponse:  # type: ignore[no-untyped-def]
    """Customers' menu: shown categories in order, each one's available dishes (R43: never a deleted one;
    a dish outside its schedule is listed with available_now False)."""
    from datetime import UTC, datetime

    from core_api.modules.catalog.schemas.restaurant import MenuCategoryResponse

    if local is None:
        local = datetime.now(UTC).astimezone((await menu_svc.restaurant_market(db, restaurant))[1])
    live = [i for i in restaurant.menu_items if i.deleted_at is None]
    groups = await menu_svc.groups_for_items(db, [i.id for i in live])
    by_id = {c.id: c for c in restaurant.categories}
    order = lambda i: (i.sort_order, i.name)  # noqa: E731
    categories = [
        MenuCategoryResponse(
            id=cat.id,
            restaurant_id=cat.restaurant_id,
            name=cat.name,
            description=cat.description,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            available_from=cat.available_from,
            available_until=cat.available_until,
            items=[item_out(item, groups.get(item.id, []), cat, local)
                   for item in sorted(cat.items, key=order) if item.is_available and item.deleted_at is None],
        )
        for cat in sorted(restaurant.categories, key=lambda c: (c.sort_order, c.name))
        if cat.is_active
    ]

    uncategorized = [
        item_out(item, groups.get(item.id, []), None, local)
        for item in sorted(live, key=order)
        if (item.category_id is None or item.category_id not in by_id) and item.is_available
    ]

    return RestaurantMenuResponse(
        restaurant=(await _public(db, [restaurant]))[0],
        categories=categories,
        uncategorized_items=uncategorized,
    )


def item_out(item, groups, category=None, local=None) -> MenuItemResponse:  # type: ignore[no-untyped-def]
    base = MenuItemResponse.model_validate(item)
    return base.model_copy(update={
        "option_groups": [menu_svc.group_out(g) for g in groups],
        "customizations": menu_svc.legacy_customizations(groups),
        "sold_out_today": menu_svc.is_sold_out(item),
        "schedule": edit.schedule_of(item, category),
        "available_now": True if local is None else edit.served_now(item, category, local),
    })


@router.post("", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    data: RestaurantCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> RestaurantResponse:
    if current_user.role != "restaurant_owner" and not authz.can(access.assignments(current_user), "partners.edit",
                                                                 data.country):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant owners (or partner admins) only")
    from core_api.modules.markets.service import countries

    country = await countries.require_open(db, data.country)  # a Markets country, not a draft
    countries.require_currency_of(country, data.currency)
    if data.address.country != country.code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "ADDRESS_COUNTRY_MISMATCH", "message": "The address is in another country"})
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


def _own_photos(user: CurrentUser, owner_id: uuid.UUID | None, *urls: str | None) -> None:
    """R22 (S13): an uploaded photo is the caller's own or the kitchen owner's, never another account's."""
    from core_api.modules.catalog.service.photo_urls import PhotoUrlError, check

    for u in urls:
        try:
            check(u, {user.id} | ({owner_id} if owner_id else set()))
        except PhotoUrlError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "PHOTO_URL", "message": str(e)})


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
async def update_restaurant(
    restaurant_id: uuid.UUID,
    data: RestaurantUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> RestaurantResponse:
    r = await access.manage(db, current_user, restaurant_id)
    _own_photos(current_user, r.owner_id, data.logo_url, data.cover_url)
    if data.status is not None:
        # R21 security review (S4): going live, suspending or un-suspending is an admin's call
        # (approve / reject, partners.edit in the city), never the owner's.
        await access.administer(db, current_user, restaurant_id)
    repo = RestaurantRepository(db)

    update_data = data.model_dump(exclude_none=True)
    updated = await repo.update(restaurant_id, **update_data)
    await cache_delete_pattern(f"restaurants:{restaurant_id}")
    await cache_delete_pattern("restaurants:list:*")
    return RestaurantResponse.model_validate(updated)


@router.put("/{restaurant_id}/pricing", response_model=RestaurantResponse)
async def configure_pricing(
    restaurant_id: uuid.UUID,
    data: PricingConfigRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> RestaurantResponse:
    """Configure a restaurant's commission / fee model (restaurant-friendly pricing)."""
    await access.manage(db, current_user, restaurant_id)
    missing = data.require_fields_for_model()
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=missing)
    repo = RestaurantRepository(db)

    values: dict = {"pricing_model": data.pricing_model}
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> MenuItemResponse:
    """Add a dish. R43: the price rules (more than 0, 2 decimals, whole rupees in India); a category_id
    of this restaurant sets the category's name too; a schedule needs both times. Goes to the menu's history."""
    r = await access.manage(db, current_user, restaurant_id)
    _own_photos(current_user, r.owner_id, data.image_url)
    fields = data.model_dump()
    customizations = fields.pop("customizations", [])
    try:
        edit.check_price(data.price, r.currency)
        edit.check_window(data.available_from, data.available_until)
        if data.category_id is not None:
            fields["category"] = (await _category(db, restaurant_id, data.category_id)).name
    except edit.RuleError as e:
        raise _rule_error(e)
    item = await MenuItemRepository(db).create(restaurant_id=restaurant_id, **fields)
    if customizations:
        try:
            await menu_svc.groups_from_legacy(db, item, customizations)
        except menu_svc.MenuError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    await edit.record(db, r, current_user, entity="dish", entity_id=item.id, name=item.name, action="added",
                      changes=[{"field": k, "old": None, "new": v} for k, v in edit.snapshot(item, edit.DISH_FIELDS).items()
                               if v not in (None, "", False)])
    groups = await menu_svc.groups_for_items(db, [item.id])
    return item_out(item, groups.get(item.id, []))


def _rule_error(e: "edit.RuleError") -> HTTPException:
    status_code = status.HTTP_409_CONFLICT if e.code == "PRICE_CONFIRM" else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=status_code, detail={"code": e.code, "message": str(e), **e.details})


async def _category(db: AsyncSession, restaurant_id: uuid.UUID, category_id: uuid.UUID):  # type: ignore[no-untyped-def]
    from core_api.modules.catalog.models.menu import MenuCategory

    c = await db.get(MenuCategory, category_id)
    if c is None or c.restaurant_id != restaurant_id:
        raise edit.RuleError("NO_SUCH_CATEGORY", "That category isn't on this menu")
    return c


NULLABLE_ON_UPDATE = ("spice_level", "available_from", "available_until", "image_url")


@router.put("/{restaurant_id}/menu-items/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    data: MenuItemUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> MenuItemResponse:
    """Change a dish. R43: the price rules; a price changed by more than 50% answers 409 PRICE_CONFIRM
    (old, new, percent) until it's sent again with confirm_price_change; every changed field goes to the
    menu's history (old and new)."""
    r = await access.manage(db, current_user, restaurant_id)
    _own_photos(current_user, r.owner_id, data.image_url)
    item_repo = MenuItemRepository(db)
    current = await item_repo.get_by_id(item_id)
    if not current or current.restaurant_id != restaurant_id or current.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    before = edit.snapshot(current, edit.DISH_FIELDS)
    fields = data.model_dump(exclude_none=True)
    fields.pop("confirm_price_change", None)
    for f in NULLABLE_ON_UPDATE:  # sent as null: cleared
        if f in data.model_fields_set and getattr(data, f) is None:
            fields[f] = None
    customizations = fields.pop("customizations", None)
    try:
        if data.price is not None:
            edit.check_price(data.price, r.currency)
            edit.confirm_needed(current.price, data.price, data.confirm_price_change)
        edit.check_window(fields.get("available_from", current.available_from),
                          fields.get("available_until", current.available_until))
        if data.category_id is not None:
            fields["category"] = (await _category(db, restaurant_id, data.category_id)).name
    except edit.RuleError as e:
        raise _rule_error(e)
    item = await item_repo.update(item_id, **fields)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    await db.refresh(item)
    if customizations is not None:
        try:
            await menu_svc.groups_from_legacy(db, item, customizations)
        except menu_svc.MenuError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    await edit.record(db, r, current_user, entity="dish", entity_id=item.id, name=item.name, action="changed",
                      changes=edit.diff(before, edit.snapshot(item, edit.DISH_FIELDS)))
    groups = await menu_svc.groups_for_items(db, [item.id])
    return item_out(item, groups.get(item.id, []))


@router.delete("/{restaurant_id}/menu-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> None:
    """Take a dish off the menu. R43: a soft delete: the row stays (deleted_at), so orders, statements and the
    history keep its name and price; customers can't see or order it."""
    from datetime import UTC, datetime

    r = await access.manage(db, current_user, restaurant_id)
    current = await MenuItemRepository(db).get_by_id(item_id)
    if not current or current.restaurant_id != restaurant_id or current.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    current.deleted_at = datetime.now(UTC)
    await db.flush()
    await edit.record(db, r, current_user, entity="dish", entity_id=current.id, name=current.name, action="deleted",
                      changes=[{"field": "price", "old": f"{current.price:.2f}", "new": None}])


@router.post("/{restaurant_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    restaurant_id: uuid.UUID,
    data: ReviewCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ReviewResponse:
    # Only the customer who ordered, for a delivered order from this restaurant.
    from core_api.modules.orders.models.order import Order

    order = await db.get(Order, data.order_id)
    if order is None or order.customer_id != current_user.id or order.restaurant_id != restaurant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "delivered":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You can review an order once it's delivered")
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
)
async def approve_restaurant(
    restaurant_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RestaurantResponse:
    await access.administer(db, current_user, restaurant_id)
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
    from datetime import UTC, datetime

    from core_api.modules.catalog.service import permits

    # R39: where a food permit is required (the US), only with an approved, unexpired one
    problem = permits.problem(restaurant, datetime.now(UTC).date(), await permits.required(db, restaurant.country))
    if problem:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "FOOD_PERMIT", "message": f"{problem}: review it first"})
    updated = await repo.update(restaurant_id, status="active")
    logger.info("restaurant_approved", restaurant_id=str(restaurant_id))
    return RestaurantResponse.model_validate(updated)


@router.post(
    "/{restaurant_id}/reject",
    response_model=RestaurantResponse,
)
async def reject_restaurant(
    restaurant_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> RestaurantResponse:
    await access.administer(db, current_user, restaurant_id)
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
)
async def list_pending_restaurants(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RestaurantResponse]:
    """Admin: restaurants pending approval in the cities the admin looks after."""
    if not authz.scopes_with(access.assignments(current_user), "partners.view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    repo = RestaurantRepository(db)
    restaurants = await repo.list_pending_restaurants(limit=limit, offset=offset)
    mine = [r for r in restaurants if await access.admin_may(db, current_user, r, "partners.view")]
    return [RestaurantResponse.model_validate(r) for r in mine]


@router.get("/admin/kitchens", response_model=RestaurantListResponse)
async def list_kitchens_for_admins(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    city: str | None = Query(None),
    country: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> RestaurantListResponse:
    """Admin: live kitchens (paused ones too) with the full record — licence expiry,
    commission terms — cut to the cities the admin may view partners in. The
    public list leaves those fields out (PublicRestaurant)."""
    from sqlalchemy import func, select

    from core_api.modules.catalog.models.restaurant import Restaurant

    if not authz.scopes_with(access.assignments(current_user), "partners.view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    q = select(Restaurant).where(Restaurant.status == "active", Restaurant.deleted_at.is_(None))
    if city:
        q = q.where(func.lower(Restaurant.city) == city.lower())
    if country:
        q = q.where(Restaurant.country == country)
    rows = (await db.execute(q.order_by(Restaurant.name))).scalars().all()
    mine = [r for r in rows if await access.admin_may(db, current_user, r, "partners.view")]
    total = len(mine)
    items = mine[(page - 1) * limit: page * limit]
    return RestaurantListResponse(items=[RestaurantResponse.model_validate(r) for r in items], total=total, page=page,
                                  limit=limit, total_pages=math.ceil(total / limit) if total else 0)
