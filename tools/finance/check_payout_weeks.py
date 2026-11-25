"""R41: list payout runs that aren't a Monday-to-Monday week, runs that overlap, and orders on more than one run.
Read-only: it changes nothing (migration 0054 lists the same when it runs; fixing old rows is a person's decision).

    cd backend && DATABASE_URL=... uv run python ../tools/finance/check_payout_weeks.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))

CHECKS = {
    "runs that are not Monday to Monday": """
        SELECT country, period_start, period_end, status, to_char(period_start, 'Dy') FROM payout_runs
        WHERE extract(isodow FROM period_start) <> 1 OR period_end <> period_start + 7 ORDER BY country, period_start""",
    "overlapping runs": """
        SELECT a.country, a.period_start, a.period_end, b.period_start, b.period_end FROM payout_runs a
        JOIN payout_runs b ON a.country = b.country AND a.id < b.id AND a.period_start < b.period_end AND b.period_start < a.period_end""",
    "orders on more than one run": """
        SELECT line->>'order_id', count(DISTINCT s.run_id) FROM payout_statements s, jsonb_array_elements(s.lines) AS line
        WHERE s.payee_type = 'restaurant' AND line ? 'order_id' GROUP BY 1 HAVING count(DISTINCT s.run_id) > 1""",
    "runs per year (a week from another year read as this year's)": """
        SELECT country, extract(year FROM period_start)::int AS year, count(*) FROM payout_runs GROUP BY 1, 2 ORDER BY 1, 2""",
    "orders delivered in the future": """
        SELECT id, actual_delivery_time FROM orders WHERE actual_delivery_time > now() + interval '1 minute'""",
}


async def main() -> int:
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    problems = 0
    async with AsyncSessionLocal() as db:
        for title, q in CHECKS.items():
            found = (await db.execute(text(q))).all()
            informational = title.startswith("runs per year")
            problems += 0 if informational else len(found)
            print(f"{title}: {len(found) if not informational else ''}")
            for r in found[:40]:
                print("   ", tuple(r))
    print("OK" if not problems else f"{problems} problem(s) listed (nothing was changed)")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
