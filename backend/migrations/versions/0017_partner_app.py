"""P19: pause until, busy minutes, GSTIN on restaurants; weekly spend per promotion.

Revision ID: 0017_partner_app
Revises: 0016_rider_app
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0017_partner_app'
down_revision: Union[str, None] = '0016_rider_app'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('restaurants', sa.Column('paused_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('restaurants', sa.Column('busy_extra_minutes', sa.Integer(), server_default='0', nullable=False))
    op.add_column('restaurants', sa.Column('busy_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('restaurants', sa.Column('gstin', sa.String(length=15), nullable=True))
    op.add_column('restaurants', sa.Column('fssai_document_key', sa.String(length=300), nullable=True))
    op.create_table(
        'promotion_spend_week',
        sa.Column('rule_key', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('spent', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('orders', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('rule_key', 'week_start'),
    )


def downgrade() -> None:
    op.drop_table('promotion_spend_week')
    op.drop_column('restaurants', 'fssai_document_key')
    op.drop_column('restaurants', 'gstin')
    op.drop_column('restaurants', 'busy_until')
    op.drop_column('restaurants', 'busy_extra_minutes')
    op.drop_column('restaurants', 'paused_until')
