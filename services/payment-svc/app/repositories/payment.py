import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentIntent, Wallet, WalletTransaction

_CENTS = Decimal("0.01")


DEMO_WALLET_SEED_AMOUNT = Decimal("1000.00")
DEMO_WALLET_SEED_REFERENCE_ID = "SPR-03B-WALLET-01-DEMO-SEED"
DEMO_WALLET_SEED_REFERENCE_TYPE = "demo_seed"


def _money(value: object) -> Decimal:
    """Coerce a numeric input to an exact 2-decimal money Decimal (major units)."""
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_intent(self, **kwargs) -> PaymentIntent:  # type: ignore[no-untyped-def]
        intent = PaymentIntent(**kwargs)
        self.session.add(intent)
        await self.session.flush()
        await self.session.refresh(intent)
        return intent

    async def get_by_id(self, intent_id: uuid.UUID) -> PaymentIntent | None:
        result = await self.session.execute(select(PaymentIntent).where(PaymentIntent.id == intent_id))
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: uuid.UUID) -> PaymentIntent | None:
        result = await self.session.execute(
            select(PaymentIntent).where(PaymentIntent.order_id == order_id).order_by(PaymentIntent.created_at.desc())
        )
        return result.scalars().first()

    async def get_by_idempotency_key(self, key: str) -> PaymentIntent | None:
        result = await self.session.execute(select(PaymentIntent).where(PaymentIntent.idempotency_key == key))
        return result.scalar_one_or_none()

    async def get_by_provider_id(self, provider_id: str) -> PaymentIntent | None:
        result = await self.session.execute(
            select(PaymentIntent).where(PaymentIntent.provider_payment_id == provider_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, intent_id: uuid.UUID, status: str) -> PaymentIntent | None:
        await self.session.execute(update(PaymentIntent).where(PaymentIntent.id == intent_id).values(status=status))
        return await self.get_by_id(intent_id)


class WalletRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, user_id: uuid.UUID, currency: str = "USD", *, for_update: bool = False) -> Wallet:
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        if for_update:
            # Lock the wallet row so concurrent credit/debit serialize and cannot race
            # on the read-modify-write of the balance (no-op on backends without FOR UPDATE).
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        wallet = result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(user_id=user_id, currency=currency, balance=Decimal("0"))
            self.session.add(wallet)
            await self.session.flush()
            await self.session.refresh(wallet)
        return wallet


    async def ensure_demo_seeded(self, user_id: uuid.UUID, currency: str = "USD", amount: Decimal = DEMO_WALLET_SEED_AMOUNT) -> Wallet:
        """Ensure a non-production demo wallet has one idempotent seed credit.

        Existing wallets created before this stage are also seeded once. The seed is
        tracked as a wallet transaction so the ledger explains why the balance exists.
        """
        amount = _money(amount)
        wallet = await self.get_or_create(user_id, currency=currency, for_update=True)
        seed_exists_result = await self.session.execute(
            select(WalletTransaction.id)
            .where(
                WalletTransaction.user_id == user_id,
                WalletTransaction.reference_id == DEMO_WALLET_SEED_REFERENCE_ID,
                WalletTransaction.reference_type == DEMO_WALLET_SEED_REFERENCE_TYPE,
            )
            .limit(1)
        )
        if seed_exists_result.scalar_one_or_none() is None:
            wallet.currency = currency
            wallet.balance = _money(_money(wallet.balance) + amount)
            tx = WalletTransaction(
                user_id=user_id,
                type="credit",
                amount=amount,
                currency=currency,
                balance_after=wallet.balance,
                description="SPR-03B demo wallet seed",
                reference_id=DEMO_WALLET_SEED_REFERENCE_ID,
                reference_type=DEMO_WALLET_SEED_REFERENCE_TYPE,
            )
            self.session.add(tx)
            await self.session.flush()
            await self.session.refresh(wallet)
        return wallet

    async def credit(self, user_id: uuid.UUID, amount: float | Decimal, description: str, reference_id: str | None = None, reference_type: str | None = None) -> tuple[Wallet, WalletTransaction]:
        amount = _money(amount)
        wallet = await self.get_or_create(user_id, for_update=True)
        wallet.balance = _money(_money(wallet.balance) + amount)
        tx = WalletTransaction(
            user_id=user_id,
            type="credit",
            amount=amount,
            currency=wallet.currency,
            balance_after=wallet.balance,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.session.add(tx)
        await self.session.flush()
        await self.session.refresh(wallet)
        await self.session.refresh(tx)
        return wallet, tx

    async def debit(self, user_id: uuid.UUID, amount: float | Decimal, description: str, reference_id: str | None = None, reference_type: str | None = None) -> tuple[Wallet, WalletTransaction]:
        amount = _money(amount)
        # Lock the row first: the balance check and decrement must be atomic, otherwise two
        # concurrent debits can both pass the check and overdraw the wallet.
        wallet = await self.get_or_create(user_id, for_update=True)
        if wallet.balance < amount:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail={"code": "INSUFFICIENT_WALLET_BALANCE", "message": "Insufficient wallet balance"})
        wallet.balance = _money(_money(wallet.balance) - amount)
        tx = WalletTransaction(
            user_id=user_id,
            type="debit",
            amount=amount,
            currency=wallet.currency,
            balance_after=wallet.balance,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.session.add(tx)
        await self.session.flush()
        await self.session.refresh(wallet)
        await self.session.refresh(tx)
        return wallet, tx

    async def list_transactions(self, user_id: uuid.UUID, page: int = 1, limit: int = 20) -> tuple[list[WalletTransaction], int]:
        where = WalletTransaction.user_id == user_id
        total = (await self.session.execute(select(func.count(WalletTransaction.id)).where(where))).scalar_one()
        result = await self.session.execute(
            select(WalletTransaction).where(where).order_by(WalletTransaction.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
        return result.scalars().all(), total  # type: ignore[return-value]
