"""Dispatch pools: users.dispatch_pool. NULL for every real rider (and everyone
else); "demo_sim" for the demo rider simulator's own riders, which only the demo
seed writes (tools/seed/demo.py, never in production). Realtime offers an order
only to riders of the order's pool: simulator orders to simulator riders, every
other order to riders with no pool (backend/realtime/app/services/dispatch.py,
same_pool). No backfill: every existing row is NULL, so nothing changes for them.

Revision ID: 0028_user_dispatch_pool
Revises: 0027_country_payout_provider
"""
import sqlalchemy as sa
from alembic import op

revision = "0028_user_dispatch_pool"
down_revision = "0027_country_payout_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("dispatch_pool", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "dispatch_pool")
