"""R19: account deletion for kitchen owners and delivery partners on Postgres: the
lookups delete_account asks first (kitchens owned, payouts not paid yet, orders in
progress) and the kitchen closing when its owner goes. The flow itself (409 while
money is owed, documents and their photos removed) is in
core_api/modules/identity/tests/test_account.py."""
import os
import uuid
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_owed_payouts_orders_in_progress_and_the_kitchen_closing() -> None:
    from sqlalchemy import delete

    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service import lookup as catalog_lookup
    from core_api.modules.finance.models import PayoutRun, PayoutStatement
    from core_api.modules.finance.service import lookup as finance_lookup
    from core_api.modules.orders.service import lookup as order_lookup
    from shared.db import AsyncSessionLocal

    owner, rider = uuid.uuid4(), uuid.uuid4()
    start = date(1979, 12, 31) + timedelta(weeks=uuid.uuid4().int % 500)  # a Monday, far from real weeks
    async with AsyncSessionLocal() as db:
        kitchen = Restaurant(name="Departing Kitchen", slug=f"departing-{owner.hex[:8]}", owner_id=owner,
                             address={"street": "1 Test St", "city": "Nowhere"}, country="US", city="Nowhere",
                             status="active", is_active=True, is_open=True)
        gone = Restaurant(name="Old Kitchen", slug=f"old-{owner.hex[:8]}", owner_id=owner, address={}, country="US",
                          city="Nowhere", status="active", is_active=False)
        db.add_all([kitchen, gone])
        await db.flush()
        gone.deleted_at = gone.created_at  # deleted long ago: not counted
        run = PayoutRun(country="US", currency="USD", period_start=start, period_end=start + timedelta(days=7),
                        status="approved", totals={}, created_by=uuid.UUID(int=0))
        db.add(run)
        await db.flush()
        db.add_all([
            PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=kitchen.id, payee_name="", currency="USD",
                            amount=4200, summary={}, lines=[], status="no_account"),
            PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=kitchen.id, payee_name="", currency="USD",
                            amount=999, summary={}, lines=[], status="paid"),  # paid already: not owed
            PayoutStatement(run_id=run.id, payee_type="rider", payee_id=rider, payee_name="", currency="USD",
                            amount=1500, summary={}, lines=[], status="pending"),
        ])
        await db.flush()
        try:
            ids = await catalog_lookup.owned_restaurant_ids(db, owner)
            assert ids == [kitchen.id]
            assert await finance_lookup.money_owed(db, restaurant_ids=ids) == {"USD": 4200}
            assert await finance_lookup.money_owed(db, rider_id=rider) == {"USD": 1500}
            assert await finance_lookup.money_owed(db, rider_id=uuid.uuid4()) == {}
            assert await finance_lookup.money_owed(db) == {}
            assert await order_lookup.orders_in_progress(db, driver_id=rider, restaurant_ids=ids) == 0

            assert await catalog_lookup.close_for_departed_owner(db, owner) == 1
            await db.refresh(kitchen)
            assert (kitchen.is_open, kitchen.is_active, kitchen.paused_reason) == (False, False, catalog_lookup.OWNER_DELETED)
        finally:
            await db.execute(delete(PayoutStatement).where(PayoutStatement.run_id == run.id))
            await db.execute(delete(PayoutRun).where(PayoutRun.id == run.id))
            await db.execute(delete(Restaurant).where(Restaurant.owner_id == owner))
            await db.commit()
