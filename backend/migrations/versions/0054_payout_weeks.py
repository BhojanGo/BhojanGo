"""R41: payout weeks. Adds a table and a constraint; changes no existing row.

* payout_run_orders (order_id primary key): an order belongs to at most one payout run. Filled as runs are
  prepared from now on (finance/service/payouts.py create_run); older runs are checked through their statements.
* ck_payout_runs_monday_week: a run is Monday to the next Monday. Added NOT VALID, so runs made before it are not
  checked or changed: they are listed instead (below, in the migration log, and by
  tools/finance/check_payout_weeks.py), for a person to decide.

Revision ID: 0054_payout_weeks
Revises: 0053_disputes_permits
"""
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0054_payout_weeks"
down_revision = "0053_disputes_permits"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

MISALIGNED = """
SELECT country, period_start, period_end, status FROM payout_runs
WHERE extract(isodow FROM period_start) <> 1 OR period_end <> period_start + 7 ORDER BY country, period_start"""
OVERLAPPING = """
SELECT a.country, a.period_start, a.period_end, b.period_start, b.period_end FROM payout_runs a
JOIN payout_runs b ON a.country = b.country AND a.id < b.id AND a.period_start < b.period_end AND b.period_start < a.period_end
ORDER BY a.country, a.period_start"""
IN_TWO_RUNS = """
SELECT line->>'order_id' AS order_id, count(DISTINCT s.run_id) FROM payout_statements s, jsonb_array_elements(s.lines) AS line
WHERE s.payee_type = 'restaurant' AND line ? 'order_id' GROUP BY 1 HAVING count(DISTINCT s.run_id) > 1"""


def upgrade() -> None:
    bind = op.get_bind()
    for title, q in (("payout runs that are not Monday to Monday", MISALIGNED), ("overlapping payout runs", OVERLAPPING),
                     ("orders on more than one payout run", IN_TWO_RUNS)):
        rows = bind.execute(sa.text(q)).all()
        log.warning("R41 check: %d %s%s", len(rows), title, "".join(f"\n  {tuple(r)}" for r in rows[:50]))
    op.create_table(
        "payout_run_orders",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["payout_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index("ix_payout_run_orders_run_id", "payout_run_orders", ["run_id"])
    op.execute("ALTER TABLE payout_runs ADD CONSTRAINT ck_payout_runs_monday_week "
               "CHECK (extract(isodow from period_start) = 1 AND period_end = period_start + 7) NOT VALID")


def downgrade() -> None:
    op.execute("ALTER TABLE payout_runs DROP CONSTRAINT IF EXISTS ck_payout_runs_monday_week")
    op.drop_index("ix_payout_run_orders_run_id", table_name="payout_run_orders")
    op.drop_table("payout_run_orders")
