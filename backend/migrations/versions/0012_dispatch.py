"""P14 dispatch: pickup and drop-off points on orders, when a rider was assigned.

Revision ID: 0012_dispatch
Revises: 0011_payouts
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0012_dispatch'
down_revision: Union[str, None] = '0011_payouts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('rider_assigned_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('pickup_lat', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('pickup_lng', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('delivery_lat', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('delivery_lng', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'delivery_lng')
    op.drop_column('orders', 'delivery_lat')
    op.drop_column('orders', 'pickup_lng')
    op.drop_column('orders', 'pickup_lat')
    op.drop_column('orders', 'rider_assigned_at')
