"""Order ratings (web v3, item 10): the customer rates the kitchen of a
delivered order, 1-5 stars and an optional short comment. One rating per
order (the ``reviews`` row keyed by order_id), editable for 7 days. The
kitchen's ``rating`` and ``review_count`` are recomputed from real ratings on
every save.

Public pages show stars only once a kitchen has enough ratings to mean
something: ``rating_display`` is ``{"new": true}`` below 5 ratings, else
``{"new": false, "stars": 4.6, "count": 23}``.
"""
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.review import Review

MIN_RATINGS_FOR_STARS = 5
EDIT_WINDOW = timedelta(days=7)
COMMENT_MAX = 500


class RatingDisplay(BaseModel):
    """What a public kitchen card shows: "New" or the stars and how many rated."""

    new: bool
    stars: float | None = None  # one decimal, e.g. 4.6
    count: int | None = None


def rating_display(rating: float | None, review_count: int | None) -> RatingDisplay:
    """``{"new": true}`` below 5 ratings, else ``{"new": false, "stars", "count"}``.
    Use it for any public kitchen response (computed field or a card)."""
    n = int(review_count or 0)
    if n < MIN_RATINGS_FOR_STARS:
        return RatingDisplay(new=True)
    return RatingDisplay(new=False, stars=round(float(rating or 0), 1), count=n)


class RatingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def editable_until(review: Review) -> datetime:
    return review.created_at + EDIT_WINDOW


def as_dict(review: Review, now: datetime | None = None) -> dict:
    """The rating as the customer sees it (GET/POST /orders/{id}/rating, order list)."""
    now = now or datetime.now(UTC)
    until = editable_until(review)
    return {"order_id": review.order_id, "restaurant_id": review.restaurant_id, "stars": int(round(review.rating)),
            "comment": review.comment, "created_at": review.created_at, "editable_until": until,
            "editable": now < until}


async def rating_for_order(db: AsyncSession, order_id: uuid.UUID) -> Review | None:
    return (await db.execute(select(Review).where(Review.order_id == order_id))).scalar_one_or_none()


async def ratings_for_orders(db: AsyncSession, order_ids: list[uuid.UUID]) -> dict[uuid.UUID, Review]:
    """order_id -> its rating, for the customer's order list (one query)."""
    if not order_ids:
        return {}
    rows = (await db.execute(select(Review).where(Review.order_id.in_(order_ids)))).scalars()
    return {r.order_id: r for r in rows}


async def rate_order(db: AsyncSession, *, order_id: uuid.UUID, restaurant_id: uuid.UUID, customer_id: uuid.UUID,
                     customer_name: str, stars: int, comment: str | None,
                     now: datetime | None = None) -> tuple[Review, bool]:
    """Create the order's rating, or edit it within 7 days. The caller checks
    the order is the customer's and delivered. Returns (rating, created)."""
    from core_api.modules.catalog.repository.cache import cache_delete_pattern
    from core_api.modules.catalog.repository.restaurant import RestaurantRepository

    now = now or datetime.now(UTC)
    comment = (comment or "").strip() or None
    review = await rating_for_order(db, order_id)
    created = review is None
    if review is None:
        review = Review(id=uuid.uuid4(), restaurant_id=restaurant_id, order_id=order_id, customer_id=customer_id,
                        customer_name=customer_name, rating=float(stars), comment=comment)
        db.add(review)
    else:
        if review.customer_id != customer_id:
            raise RatingError("NOT_FOUND", "Order not found")
        if now >= editable_until(review):
            raise RatingError("RATING_LOCKED", "Ratings can be changed for 7 days")
        review.rating = float(stars)
        review.comment = comment
    await db.flush()
    await db.refresh(review)
    await RestaurantRepository(db).update_rating(restaurant_id)
    await cache_delete_pattern(f"restaurants:{restaurant_id}")
    return review, created
