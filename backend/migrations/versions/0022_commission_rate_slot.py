"""One commission rate slot: the most specific rate rule wins.

Rate rules (percent by tier, and the new single percent) share the slot
``commission:rate`` so a restaurant's or a city's rate replaces the country's
instead of adding to it. Order snapshots keep the slot they were priced with.

Revision ID: 0022_commission_rate_slot
Revises: 0021_ops_alerts
"""
from alembic import op

revision = "0022_commission_rate_slot"
down_revision = "0021_ops_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE rules SET slot = 'commission:rate' WHERE family = 'commission' AND template IN ('percent', 'percent_by_tier')")


def downgrade() -> None:
    op.execute("UPDATE rules SET slot = 'commission:' || template WHERE family = 'commission' AND template IN ('percent', 'percent_by_tier')")
