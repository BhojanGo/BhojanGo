import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core_api.modules.identity.api.v1.auth import limiter as auth_limiter
from core_api.modules.identity.models.account import Favourite, NotificationPreference
from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.admin_role import AdminRoleAssignment
from core_api.modules.identity.models.user import User
from core_api.modules.payments.models.payment_method import PaymentMethod
from shared.db import Base, get_db
from core_api.main import app

# ── Test database (SQLite in-memory for speed) ────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Base.metadata is shared by every core_api module (some use Postgres-only
# types), so only create identity's tables in SQLite.
IDENTITY_TABLES = [User.__table__, Address.__table__, AdminRoleAssignment.__table__, PaymentMethod.__table__,
                   Favourite.__table__, NotificationPreference.__table__]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=IDENTITY_TABLES)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=IDENTITY_TABLES)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


COUNTRIES = {
    "IN": ("INR", "+91", ("en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN", "bn-IN"), "live"),
    "US": ("USD", "+1", ("en-US", "es-US"), "live"),
    "FR": ("EUR", "+33", ("fr-FR",), "draft"),  # a country being set up: no sign-ups yet
}


async def fake_country(db, code: str):  # type: ignore[no-untyped-def]
    from core_api.modules.markets.service.countries import CountryInfo

    row = COUNTRIES.get(code)
    return CountryInfo(code, row[0], row[1], row[2], row[3]) if row else None


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Rate-limit counters are in-memory and shared across tests; start each test clean.
    auth_limiter.reset()

    # Real Redis semantics in memory (refresh families, OTP, blacklist).
    import fakeredis

    fake = fakeredis.FakeAsyncRedis(decode_responses=True)

    async def fake_get_redis():
        return fake

    with (
        patch("shared.redis.get_redis", fake_get_redis),
        patch("core_api.modules.identity.service.otp.get_redis", fake_get_redis),
        patch("core_api.modules.identity.service.auth.get_redis", fake_get_redis),
        patch("core_api.modules.identity.api.dependencies.get_redis", fake_get_redis),
        # Orders and reviews live in Postgres-only tables; account deletion's
        # changes to them are tested in core_api/integration/test_account.py.
        patch("core_api.modules.orders.service.lookup.forget_customer", AsyncMock(return_value=0)),
        patch("core_api.modules.catalog.service.lookup.forget_reviewer", AsyncMock()),
        # Markets' countries table is Postgres-only; the seeded two stand in for it here.
        patch("core_api.modules.markets.service.countries.lookup", fake_country),
        patch("core_api.modules.markets.service.countries.open_currencies", AsyncMock(return_value={"INR", "USD"})),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
