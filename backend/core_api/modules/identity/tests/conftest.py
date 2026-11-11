import asyncio
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core_api.modules.identity.api.v1.auth import limiter as auth_limiter
from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.admin_role import AdminRoleAssignment
from core_api.modules.identity.models.user import User
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
IDENTITY_TABLES = [User.__table__, Address.__table__, AdminRoleAssignment.__table__]


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
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
