"""What the worker needs to know to message someone: who they are, their
language and devices, the order, the city's time zone. Read straight from the
shared database (the worker image doesn't include core_api's models)."""
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import DeviceToken
from shared.providers.push import Device

COUNTRY_TZ = {"IN": "Asia/Kolkata", "US": "America/New_York"}


@dataclass
class Person:
    id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    locale: str
    country: str
    devices: list[Device] = field(default_factory=list)

    @property
    def first_name(self) -> str:
        return (self.name or "").split(" ")[0] or self.name


class Directory:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def person(self, user_id: uuid.UUID | str) -> Person | None:
        row = (await self.db.execute(text(
            "SELECT id, full_name, email, phone, preferred_locale, country FROM users WHERE id = :id AND is_active"),
            {"id": str(user_id)})).first()
        if row is None:
            return None
        tokens = (await self.db.execute(select(DeviceToken.token, DeviceToken.provider)
                                        .where(DeviceToken.user_id == row.id))).all()
        return Person(row.id, row.full_name, row.email, row.phone, row.preferred_locale, row.country,
                      [Device(t, p) for t, p in tokens])

    async def order(self, order_id: str) -> dict | None:
        row = (await self.db.execute(text(
            "SELECT id, customer_id, restaurant_id, restaurant_name, total, currency, market_city, "
            "estimated_delivery_time, accept_due_at, driver_id, items FROM orders WHERE id = :id"),
            {"id": order_id})).mappings().first()
        return dict(row) if row else None

    async def restaurant_owner(self, restaurant_id: str) -> uuid.UUID | None:
        return (await self.db.execute(text("SELECT owner_id FROM restaurants WHERE id = :id"),
                                      {"id": restaurant_id})).scalar()

    async def timezone(self, city: str | None, country: str | None = None) -> str:
        if city:
            tz = (await self.db.execute(text(
                "SELECT coalesce(c.timezone, r.timezone, co.timezone) FROM cities c "
                "JOIN regions r ON r.id = c.region_id JOIN countries co ON co.id = c.country_id WHERE c.code = :code"),
                {"code": city})).scalar()
            if tz:
                return tz
        code = country or (city or "")[:2]
        tz = (await self.db.execute(text("SELECT timezone FROM countries WHERE code = :c"), {"c": code})).scalar()
        return tz or COUNTRY_TZ.get(code, "UTC")

    async def payout_period(self, run_id: str) -> tuple[date, date] | None:
        row = (await self.db.execute(text("SELECT period_start, period_end FROM payout_runs WHERE id = :id"),
                                     {"id": run_id})).first()
        return (row[0], row[1]) if row else None

    async def forget_devices(self, tokens: list[str]) -> None:
        """Tokens a push service says are dead (app uninstalled, token rotated)."""
        if tokens:
            await self.db.execute(delete(DeviceToken).where(DeviceToken.token.in_(tokens)))
