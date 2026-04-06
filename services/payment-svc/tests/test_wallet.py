import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base, get_db
from app.main import app

TEST_DB = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_wallet_credit_and_debit(db_session: AsyncSession) -> None:
    from app.repositories.payment import WalletRepository

    repo = WalletRepository(db_session)
    user_id = uuid.uuid4()

    # Credit
    wallet, tx = await repo.credit(user_id, 100.0, "Test credit")
    assert wallet.balance == 100.0
    assert tx.type == "credit"
    assert tx.balance_after == 100.0

    # Debit
    wallet2, tx2 = await repo.debit(user_id, 30.0, "Test debit")
    assert wallet2.balance == 70.0
    assert tx2.type == "debit"


@pytest.mark.asyncio
async def test_wallet_insufficient_balance(db_session: AsyncSession) -> None:
    from fastapi import HTTPException

    from app.repositories.payment import WalletRepository

    repo = WalletRepository(db_session)
    user_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await repo.debit(user_id, 500.0, "Should fail")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INSUFFICIENT_WALLET_BALANCE"


@pytest.mark.asyncio
async def test_wallet_get_or_create_idempotent(db_session: AsyncSession) -> None:
    from app.repositories.payment import WalletRepository

    repo = WalletRepository(db_session)
    user_id = uuid.uuid4()

    w1 = await repo.get_or_create(user_id)
    w2 = await repo.get_or_create(user_id)
    assert w1.id == w2.id
