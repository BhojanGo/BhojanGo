"""Batch rider pay (item 2): an order's place in a batch and its batch bonus.

The first drop-off of a batch is paid as usual; later ones pay no base, but
distance + waiting + the city's ``rider_pay:batch_bonus`` (recorded when the rider
accepts, so a later rule change doesn't move pay already earned).

Revision ID: 0024_order_batch_position
Revises: 0023_restaurant_tier_changes
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_order_batch_position"
down_revision = "0023_restaurant_tier_changes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("orders", sa.Column("batch_position", sa.SmallInteger(), nullable=True))
    op.add_column("orders", sa.Column("batch_bonus", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "batch_bonus")
    op.drop_column("orders", "batch_position")
    op.drop_column("orders", "batch_id")
