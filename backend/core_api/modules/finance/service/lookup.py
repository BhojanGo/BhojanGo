"""Small read-only lookups other modules use instead of reading finance tables."""
import uuid
from collections import defaultdict

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.models import PayoutStatement

# A statement that still has to reach the payee (models.PayoutStatement.status).
UNPAID = ("pending", "failed", "no_account", "onboarding")


async def money_owed(db: AsyncSession, *, rider_id: uuid.UUID | None = None,
                     restaurant_ids: list[uuid.UUID] | None = None) -> dict[str, int]:
    """What we still owe this delivery partner or these kitchens on payout statements
    not paid yet, by currency, in minor units (account deletion waits for it: R19)."""
    who = []
    if rider_id is not None:
        who.append(and_(PayoutStatement.payee_type == "rider", PayoutStatement.payee_id == rider_id))
    if restaurant_ids:
        who.append(and_(PayoutStatement.payee_type == "restaurant", PayoutStatement.payee_id.in_(restaurant_ids)))
    if not who:
        return {}
    owed: dict[str, int] = defaultdict(int)
    for currency, amount in (await db.execute(select(PayoutStatement.currency, PayoutStatement.amount).where(
            or_(*who), PayoutStatement.status.in_(UNPAID), PayoutStatement.amount > 0))).all():
        owed[currency] += amount
    return dict(owed)
