import math
import uuid
from datetime import datetime

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs) -> Order:  # type: ignore[no-untyped-def]
        order = Order(**kwargs)
        self.session.add(order)
        await self.session.flush()
        await self.session.refresh(order)
        return order

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        result = await self.session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()

    async def update_status(
        self,
        order_id: uuid.UUID,
        status: str,
        **extra_fields,  # type: ignore[no-untyped-def]
    ) -> Order | None:
        values = {"status": status, **extra_fields}
        if status == "delivered":
            values["actual_delivery_time"] = datetime.utcnow()
        await self.session.execute(update(Order).where(Order.id == order_id).values(**values))
        return await self.get_by_id(order_id)

    async def list_by_customer(
        self, customer_id: uuid.UUID, page: int = 1, limit: int = 20
    ) -> tuple[list[Order], int]:
        where = Order.customer_id == customer_id
        total = (await self.session.execute(select(func.count(Order.id)).where(where))).scalar_one()
        result = await self.session.execute(
            select(Order).where(where).order_by(Order.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
        return result.scalars().all(), total  # type: ignore[return-value]

    async def list_by_restaurant(
        self, restaurant_id: uuid.UUID, page: int = 1, limit: int = 20
    ) -> tuple[list[Order], int]:
        where = Order.restaurant_id == restaurant_id
        total = (await self.session.execute(select(func.count(Order.id)).where(where))).scalar_one()
        result = await self.session.execute(
            select(Order).where(where).order_by(Order.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
        return result.scalars().all(), total  # type: ignore[return-value]

    async def pain_point_metrics(self) -> dict:
        """Aggregate pain-point metrics across all orders (admin analytics)."""
        total = (await self.session.execute(select(func.count(Order.id)))).scalar_one()
        platform_rev = (
            await self.session.execute(select(func.coalesce(func.sum(Order.platform_fee), 0)))
        ).scalar_one()
        long_dist = (
            await self.session.execute(select(func.count(Order.id)).where(Order.is_long_distance.is_(True)))
        ).scalar_one()
        avg_prep = (await self.session.execute(select(func.avg(Order.estimated_prep_minutes)))).scalar_one()
        avg_dist = (await self.session.execute(select(func.avg(Order.delivery_distance_km)))).scalar_one()
        status_rows = (
            await self.session.execute(select(Order.status, func.count(Order.id)).group_by(Order.status))
        ).all()
        return {
            "total_orders": total,
            "total_platform_revenue": float(platform_rev or 0),
            "long_distance_orders": long_dist,
            "long_distance_rate": (long_dist / total) if total else 0.0,
            "avg_estimated_prep_minutes": float(avg_prep or 0),
            "avg_delivery_distance_km": float(avg_dist or 0),
            "orders_by_status": {status: count for status, count in status_rows},
        }

    async def get_driver_active_order(self, driver_id: uuid.UUID) -> Order | None:
        result = await self.session.execute(
            select(Order).where(
                and_(
                    Order.driver_id == driver_id,
                    Order.status.in_(["ready_for_pickup", "picked_up"]),
                )
            )
        )
        return result.scalar_one_or_none()
