import math
import uuid
from typing import Sequence

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import MenuCategory, MenuItem
from app.models.restaurant import Restaurant
from app.models.review import Review


def _make_slug(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:80]


class RestaurantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, owner_id: uuid.UUID, **kwargs) -> Restaurant:  # type: ignore[no-untyped-def]
        name = kwargs.get("name", "")
        base_slug = _make_slug(name)
        slug = base_slug
        counter = 1
        while await self._slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        restaurant = Restaurant(owner_id=owner_id, slug=slug, **kwargs)
        self.session.add(restaurant)
        await self.session.flush()
        await self.session.refresh(restaurant)
        return restaurant

    async def _slug_exists(self, slug: str) -> bool:
        result = await self.session.execute(select(Restaurant.id).where(Restaurant.slug == slug))
        return result.scalar_one_or_none() is not None

    async def get_by_id(self, restaurant_id: uuid.UUID) -> Restaurant | None:
        result = await self.session.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Restaurant | None:
        result = await self.session.execute(
            select(Restaurant).where(Restaurant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_restaurants(
        self,
        city: str | None = None,
        cuisine: str | None = None,
        min_rating: float | None = None,
        max_delivery_fee: float | None = None,
        is_open: bool | None = None,
        country: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Restaurant], int]:
        conditions = [Restaurant.is_active == True]  # noqa: E712

        if city:
            conditions.append(func.lower(Restaurant.city) == city.lower())
        if country:
            conditions.append(Restaurant.country == country)
        if cuisine:
            conditions.append(Restaurant.cuisine_types.any(cuisine))  # type: ignore[union-attr]
        if min_rating is not None:
            conditions.append(Restaurant.rating >= min_rating)
        if max_delivery_fee is not None:
            conditions.append(Restaurant.delivery_fee <= max_delivery_fee)
        if is_open is not None:
            conditions.append(Restaurant.is_open == is_open)

        total_result = await self.session.execute(
            select(func.count(Restaurant.id)).where(and_(*conditions))
        )
        total = total_result.scalar_one()

        result = await self.session.execute(
            select(Restaurant)
            .where(and_(*conditions))
            .order_by(Restaurant.rating.desc(), Restaurant.review_count.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return result.scalars().all(), total  # type: ignore[return-value]

    async def get_with_menu(self, restaurant_id: uuid.UUID) -> Restaurant | None:
        result = await self.session.execute(
            select(Restaurant)
            .where(Restaurant.id == restaurant_id)
            .options(
                selectinload(Restaurant.categories).selectinload(MenuCategory.items),
                selectinload(Restaurant.menu_items),
            )
        )
        return result.scalar_one_or_none()

    async def update(self, restaurant_id: uuid.UUID, **kwargs) -> Restaurant | None:  # type: ignore[no-untyped-def]
        await self.session.execute(
            update(Restaurant).where(Restaurant.id == restaurant_id).values(**kwargs)
        )
        return await self.get_by_id(restaurant_id)

    async def update_rating(self, restaurant_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.restaurant_id == restaurant_id
            )
        )
        avg_rating, count = result.one()
        await self.session.execute(
            update(Restaurant)
            .where(Restaurant.id == restaurant_id)
            .values(rating=round(float(avg_rating or 0), 2), review_count=count)
        )


class MenuItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, restaurant_id: uuid.UUID, **kwargs) -> MenuItem:  # type: ignore[no-untyped-def]
        item = MenuItem(restaurant_id=restaurant_id, **kwargs)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> MenuItem | None:
        result = await self.session.execute(select(MenuItem).where(MenuItem.id == item_id))
        return result.scalar_one_or_none()

    async def update(self, item_id: uuid.UUID, **kwargs) -> MenuItem | None:  # type: ignore[no-untyped-def]
        await self.session.execute(update(MenuItem).where(MenuItem.id == item_id).values(**kwargs))
        return await self.get_by_id(item_id)

    async def delete(self, item_id: uuid.UUID) -> bool:
        item = await self.get_by_id(item_id)
        if not item:
            return False
        await self.session.delete(item)
        return True

    async def list_by_restaurant(self, restaurant_id: uuid.UUID) -> list[MenuItem]:
        result = await self.session.execute(
            select(MenuItem)
            .where(MenuItem.restaurant_id == restaurant_id)
            .order_by(MenuItem.sort_order, MenuItem.name)
        )
        return result.scalars().all()  # type: ignore[return-value]


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs) -> Review:  # type: ignore[no-untyped-def]
        review = Review(**kwargs)
        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def get_by_order_id(self, order_id: uuid.UUID) -> Review | None:
        result = await self.session.execute(select(Review).where(Review.order_id == order_id))
        return result.scalar_one_or_none()

    async def list_by_restaurant(self, restaurant_id: uuid.UUID, limit: int = 20) -> list[Review]:
        result = await self.session.execute(
            select(Review)
            .where(Review.restaurant_id == restaurant_id)
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()  # type: ignore[return-value]
