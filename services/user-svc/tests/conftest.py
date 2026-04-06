import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base, get_db
from app.main import app

# ── Test database (SQLite in-memory for speed) ────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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

    # Mock Redis
    with patch("app.core.redis._redis_client") as mock_redis:
        mock = AsyncMock()
        mock.ping.return_value = True
        mock.get.return_value = None
        mock.setex.return_value = True
        mock.delete.return_value = 1
        mock.exists.return_value = 0
        mock.keys.return_value = []
        mock.incr.return_value = 1
        mock.expire.return_value = True
        mock.pipeline.return_value.__aenter__ = AsyncMock(return_value=mock)
        mock.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)
        mock.pipeline.return_value.execute = AsyncMock(return_value=[1, True])

        async def mock_get_redis():
            return mock

        with patch("app.core.redis.get_redis", mock_get_redis), \
             patch("app.services.otp.get_redis", mock_get_redis), \
             patch("app.services.auth.get_redis", mock_get_redis), \
             patch("app.core.dependencies.get_redis", mock_get_redis):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                yield ac

    app.dependency_overrides.clear()
