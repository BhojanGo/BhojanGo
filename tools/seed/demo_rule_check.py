"""R27: after the demo seed ran with a kitchen's live tablet required (as on QA, where the rule is
on and no tablet is open while the reset job seeds), every demo city has order history and the
demo rider simulator has kitchens to play (worker app/demo_sim/runner.py PLAYED_KITCHENS_SQL).
Run by CI (backend-checks.yml) after `KITCHEN_TABLET_REQUIRED=1 python tools/seed/demo.py`.

    cd backend && uv run python ../tools/seed/demo_rule_check.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seed as base  # noqa: E402,F401  (puts the backend on sys.path)
from demo_data import DEMO  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

HISTORY = text("""
SELECT count(*) FROM orders o JOIN users c ON c.id = o.customer_id
WHERE c.email LIKE :pattern AND o.status = 'delivered'
""")


async def main() -> int:
    # The simulator's own query (the worker's `app` package; nothing else here is called `app`).
    sys.path.insert(0, str(Path(base.__file__).resolve().parents[2] / "backend" / "worker"))
    from app.demo_sim.runner import PLAYED_KITCHENS_SQL  # noqa: PLC0415

    engine = create_async_engine(os.environ["DATABASE_URL"])
    problems = []
    async with engine.connect() as db:
        for key in DEMO:
            delivered = (await db.execute(HISTORY, {"pattern": f"demo%.{key}@example.com"})).scalar() or 0
            played = (await db.execute(PLAYED_KITCHENS_SQL, {"email": f"demo1.{key}@example.com"})).all()
            print(f"demo {key}: {delivered} delivered orders from the demo customers; the simulator plays {len(played)} kitchens")
            if delivered == 0:
                problems.append(f"{key}: no order history (the seed was refused by the live-tablet rule?)")
            if not played:
                problems.append(f"{key}: the simulator would have no kitchen to play")
    await engine.dispose()
    for p in problems:
        print("FAIL", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
